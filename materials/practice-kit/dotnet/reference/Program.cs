// Инженерные проверки эталонного кода. Не проверяют сдаваемую работу участника.
var checks = 0;
void Equal(decimal expected, decimal actual)
{
    if (expected != actual)
    {
        throw new Exception("value");
    }
    checks++;
}
void Reject(decimal ordered, decimal completed, string parameter)
{
    try
    {
        QuantityRules.Remaining(ordered, completed);
        throw new Exception("missing rejection");
    }
    catch (ArgumentOutOfRangeException error) when (error.ParamName == parameter)
    {
        checks++;
    }
}
Equal(6m, QuantityRules.Remaining(10m, 4m));
Equal(0m, QuantityRules.Remaining(0m, 0m));
Equal(0m, QuantityRules.Remaining(10m, 10m));
Equal(1m, QuantityRules.Remaining(1.5m, .5m));
Reject(-1m, 0m, "ordered");
Reject(1m, -1m, "completed");
Reject(1m, 2m, "completed");
Console.WriteLine($"Reference engineering checks: {checks}");
