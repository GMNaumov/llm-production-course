// Эталон П7.2: сохранить имя, сигнатуру, decimal и исключения по требованию.
public static class QuantityRules
{
    public static decimal Remaining(decimal ordered, decimal completed)
    {
        if (ordered < 0m)
        {
            throw new ArgumentOutOfRangeException(nameof(ordered));
        }
        if (completed < 0m || completed > ordered)
        {
            throw new ArgumentOutOfRangeException(nameof(completed));
        }
        return ordered - completed;
    }
}
