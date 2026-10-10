/// The date part of [time], at local midnight.
DateTime dateOnly(DateTime time) => DateTime(time.year, time.month, time.day);

/// Whether both moments fall on the same calendar day.
bool isSameDay(DateTime a, DateTime b) => dateOnly(a) == dateOnly(b);

/// The calendar day [days] before [time], at local midnight. Built from the
/// date parts so daylight saving changes cannot shift it.
DateTime daysBefore(DateTime time, int days) {
  return DateTime(time.year, time.month, time.day - days);
}
