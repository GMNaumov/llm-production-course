using System.Net;

// Проверяем эталон через подставной HTTP transport, без сети и секретов.
var checks = 0;
async Task CheckAsync(
    string expected,
    Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send,
    int expectedAttempts = 1,
    CancellationToken cancellationToken = default,
    TimeSpan? timeout = null)
{
    using var handler = new StubHandler(send);
    using var http = new HttpClient(handler) { BaseAddress = new Uri("http://training.invalid/") };
    var client = new OrdersClient(http, _ => Task.FromResult("synthetic-token"), timeout);
    var actual = await client.ReadAsync("TRN-0001", cancellationToken);
    if (actual != expected || handler.Attempts != expectedAttempts)
    {
        throw new Exception($"Expected {expected}/{expectedAttempts}, got {actual}/{handler.Attempts}");
    }
    checks++;
}

foreach (var (status, expected, attempts) in new[]
{
    (HttpStatusCode.OK, "ok", 1),
    (HttpStatusCode.Unauthorized, "unauthorized", 1),
    (HttpStatusCode.Forbidden, "forbidden", 1),
    (HttpStatusCode.NotFound, "not_found", 1),
    (HttpStatusCode.ServiceUnavailable, "dependency_error", 2)
})
{
    await CheckAsync(expected, (request, _) =>
    {
        if (request.Headers.Authorization?.Parameter != "synthetic-token")
        {
            throw new Exception("Missing authorization");
        }
        return Task.FromResult(new HttpResponseMessage(status) { Content = new StringContent("{}") });
    }, attempts);
}

await CheckAsync("transport_error", (_, _) => throw new HttpRequestException(), 2);
await CheckAsync("oversize", (_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
{
    Content = new ByteArrayContent(new byte[4097])
}));
// Неизвестная длина и чтение порциями: клиент должен остановиться на 4097 байтах.
var stream = new LimitedProbeStream(100_000);
await CheckAsync("oversize", (_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
{
    Content = new StreamContent(stream)
}));
if (stream.BytesRead != 4097)
{
    throw new Exception("Response was buffered beyond its limit");
}
checks++;

await CheckAsync("timeout", async (_, token) =>
{
    await Task.Delay(Timeout.InfiniteTimeSpan, token);
    return new HttpResponseMessage(HttpStatusCode.OK);
}, timeout: TimeSpan.FromMilliseconds(30));

// Отмена внутри catch/backoff раньше выходила из метода исключением.
using var cancellation = new CancellationTokenSource();
await CheckAsync("cancelled", (_, _) =>
{
    cancellation.Cancel();
    throw new HttpRequestException();
}, cancellationToken: cancellation.Token);
Console.WriteLine($"Client reference checks: {checks}");

sealed class StubHandler(
    Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send) : HttpMessageHandler
{
    public int Attempts { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
    {
        Attempts++;
        return send(request, ct);
    }
}

sealed class LimitedProbeStream(int length) : Stream
{
    public int BytesRead { get; private set; }
    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => throw new NotSupportedException();
    public override long Position
    {
        get => throw new NotSupportedException();
        set => throw new NotSupportedException();
    }

    public override int Read(byte[] buffer, int offset, int count)
    {
        var received = Math.Min(Math.Min(count, 127), length - BytesRead);
        Array.Clear(buffer, offset, received);
        BytesRead += received;
        return received;
    }

    public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken ct = default)
    {
        ct.ThrowIfCancellationRequested();
        var received = Math.Min(Math.Min(buffer.Length, 127), length - BytesRead);
        buffer.Span[..received].Clear();
        BytesRead += received;
        return ValueTask.FromResult(received);
    }

    public override void Flush() => throw new NotSupportedException();
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
}
