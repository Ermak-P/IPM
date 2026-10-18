namespace SyntheticIpm.Domain;

public sealed record UserProfile(string UserId, string Country, int Age);
public sealed class TargetingCondition
{
    public string Country { get; }
    public int MinimumAge { get; }
    public TargetingCondition(string country, int minimumAge)
    {
        Country = Campaign.Required(country);
        if (minimumAge is < 0 or > 120) throw new ArgumentOutOfRangeException(nameof(minimumAge));
        MinimumAge = minimumAge;
    }
}
public sealed record TargetAudience(string Name, TargetingCondition Condition);
public static class TargetingEvaluator
{
    public static bool Matches(TargetAudience audience, UserProfile user) =>
        !string.IsNullOrWhiteSpace(user.UserId) && user.Age <= 120 &&
        user.Age >= audience.Condition.MinimumAge &&
        string.Equals(user.Country, audience.Condition.Country, StringComparison.OrdinalIgnoreCase);
}
