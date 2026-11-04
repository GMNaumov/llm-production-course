using System.Security.Cryptography;
using System.Text;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders(); // В эталоне клиентский отчёт; содержимое/токены не журналируются.
var app = builder.Build();
app.MapGet("/live", () => Results.Ok(new { state = "alive" }));
app.MapGet("/orders/{id}", async (string id, HttpRequest request, CancellationToken ct) =>
{
    // Только учебная имитация сервисной идентичности. Токен перечитывается для ротации.
    var token = (await File.ReadAllTextAsync("/run/secrets/api-token.txt", ct)).Trim();
    var provided = request.Headers.Authorization.ToString();
    var valid = CryptographicOperations.FixedTimeEquals(
        SHA256.HashData(Encoding.UTF8.GetBytes("Bearer " + token)),
        SHA256.HashData(Encoding.UTF8.GetBytes(provided)));
    if (!valid) return Results.Unauthorized();
    if (id == "TRN-0403") return Results.StatusCode(403);
    if (id == "TRN-0503") return Results.StatusCode(503);
    if (id == "TRN-0408") await Task.Delay(TimeSpan.FromSeconds(10), ct);
    if (id != "TRN-0001") return Results.NotFound();
    return Results.Ok(new { id, status = "draft", plant = "A", quantity = 10, version = 1 });
});
app.Run();
