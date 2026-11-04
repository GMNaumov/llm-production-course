using System.Net;
using System.Net.Http.Headers;

// Учебный транспортный клиент. Права на объект проверяет API, а не модель.
public sealed class OrdersClient
{
    private readonly HttpClient http;
    private readonly Func<CancellationToken, Task<string>> readToken;
    private readonly TimeSpan timeout;

    public OrdersClient(
        HttpClient http,
        Func<CancellationToken, Task<string>> readToken,
        TimeSpan? timeout = null)
    {
        this.http = http;
        this.readToken = readToken;
        this.timeout = timeout ?? TimeSpan.FromSeconds(2);
    }

    public async Task<string> ReadAsync(string id, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(id) || id.Length > 64)
        {
            throw new ArgumentException("Invalid order identifier", nameof(id));
        }

        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(timeout);
        try
        {
            for (var attempt = 0; attempt < 2; attempt++)
            {
                try
                {
                    // Provider перечитывается на каждой попытке для поддержки ротации.
                    var token = await readToken(deadline.Token);
                    using var request = new HttpRequestMessage(
                        HttpMethod.Get, "orders/" + Uri.EscapeDataString(id));
                    request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                    using var response = await http.SendAsync(
                        request, HttpCompletionOption.ResponseHeadersRead, deadline.Token);

                    if (response.StatusCode == HttpStatusCode.Unauthorized)
                    {
                        return "unauthorized";
                    }
                    if (response.StatusCode == HttpStatusCode.Forbidden)
                    {
                        return "forbidden";
                    }
                    if (response.StatusCode == HttpStatusCode.NotFound)
                    {
                        return "not_found";
                    }
                    if ((int)response.StatusCode >= 500 && attempt == 0)
                    {
                        await Task.Delay(100 + Random.Shared.Next(50), deadline.Token);
                        continue;
                    }
                    if (!response.IsSuccessStatusCode)
                    {
                        return "dependency_error";
                    }

                    // Content-Length необязателен и не заменяет ограниченное чтение.
                    const int maxBodyBytes = 4096;
                    if (response.Content.Headers.ContentLength > maxBodyBytes)
                    {
                        return "oversize";
                    }
                    await using var body = await response.Content.ReadAsStreamAsync(deadline.Token);
                    var buffer = new byte[maxBodyBytes + 1];
                    var received = 0;
                    while (received < buffer.Length)
                    {
                        var count = await body.ReadAsync(buffer.AsMemory(received), deadline.Token);
                        if (count == 0)
                        {
                            return "ok";
                        }
                        received += count;
                    }
                    return "oversize";
                }
                catch (HttpRequestException) when (attempt == 0)
                {
                    // Отмена во время backoff обрабатывается общим catch снаружи цикла.
                    await Task.Delay(100, deadline.Token);
                }
                catch (HttpRequestException)
                {
                    return "transport_error";
                }
                catch (IOException)
                {
                    return "transport_error";
                }
            }
        }
        catch (OperationCanceledException)
        {
            return cancellationToken.IsCancellationRequested ? "cancelled" : "timeout";
        }

        return "dependency_error";
    }
}
