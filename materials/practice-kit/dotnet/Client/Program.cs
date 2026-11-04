using var http = new HttpClient { BaseAddress = new Uri("http://api:8090/") };
var client = new OrdersClient(http, async cancellationToken =>
    (await File.ReadAllTextAsync("/run/secrets/api-token.txt", cancellationToken)).Trim());
foreach (var id in new[] { "TRN-0001", "TRN-0403", "TRN-0503", "TRN-0408", "TRN-9999" })
{
    var outcome = await client.ReadAsync(id, CancellationToken.None);
    Console.WriteLine($"{id}: {outcome}");
}
