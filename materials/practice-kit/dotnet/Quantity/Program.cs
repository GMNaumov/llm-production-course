var observations = new (decimal Ordered, decimal Completed)[] { (10m, 4m), (0m, 0m), (1.5m, 0.5m) };
foreach (var item in observations)
    Console.WriteLine($"{item.Ordered}-{item.Completed}={QuantityRules.Remaining(item.Ordered, item.Completed)}");
