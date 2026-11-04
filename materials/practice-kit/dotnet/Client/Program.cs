using System.Net;
using System.Net.Http.Headers;

using var http = new HttpClient { BaseAddress = new Uri("http://api:8090/") };
foreach (var id in new[] { "TRN-0001", "TRN-0403", "TRN-0503", "TRN-0408", "TRN-9999" })
{
    var outcome = await ReadAsync(id, CancellationToken.None);
    Console.WriteLine($"{id}: {outcome}");
}

async Task<string> ReadAsync(string id, CancellationToken cancellationToken)
{
    if (string.IsNullOrWhiteSpace(id) || id.Length > 64) throw new ArgumentException("id");
    using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
    deadline.CancelAfter(TimeSpan.FromSeconds(2));
    for (var attempt = 0; attempt < 2; attempt++)
    {
        try
        {
            // Учебный файловый provider перечитывается при каждом запросе.
            var token = (await File.ReadAllTextAsync("/run/secrets/api-token.txt", deadline.Token)).Trim();
            using var request = new HttpRequestMessage(HttpMethod.Get, "orders/" + Uri.EscapeDataString(id));
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, deadline.Token);
            if (response.StatusCode == HttpStatusCode.Unauthorized) return "unauthorized";
            if (response.StatusCode == HttpStatusCode.Forbidden) return "forbidden";
            if (response.StatusCode == HttpStatusCode.NotFound) return "not_found";
            if ((int)response.StatusCode >= 500 && attempt == 0)
            {
                await Task.Delay(100 + Random.Shared.Next(50), deadline.Token);
                continue;
            }
            if (!response.IsSuccessStatusCode) return "dependency_error";
            // Здесь контракт мал; ограничение реального API настраивается отдельно.
            var bytes = await response.Content.ReadAsByteArrayAsync(deadline.Token);
            return bytes.Length <= 4096 ? "ok" : "oversize";
        }
        catch (OperationCanceledException) { return "timeout_or_cancelled"; }
        catch (HttpRequestException) when (attempt == 0) { await Task.Delay(100, deadline.Token); }
        catch (HttpRequestException) { return "transport_error"; }
    }
    return "dependency_error";
}
