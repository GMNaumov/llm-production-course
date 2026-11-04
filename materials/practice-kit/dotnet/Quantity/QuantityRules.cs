public static class QuantityRules
{
    // Исходное требование: неотрицательные количества, completed <= ordered.
    // Учебный baseline намеренно не проверяет границы.
    public static decimal Remaining(decimal ordered, decimal completed) => ordered - completed;
}
