import 'package:flutter/material.dart';

/// VoxScribe's color tokens, one set per brightness.
///
/// Values mirror the desktop app. Two rules keep contrast safe:
/// - [accent] is a fill only, always with [onAccent] text on top.
/// - Where green is text, an icon or a thin line on [background], use
///   [accentInk], which is darker in light mode so it stays readable.
@immutable
class VoxColors extends ThemeExtension<VoxColors> {
  const VoxColors({
    required this.background,
    required this.card,
    required this.raised,
    required this.border,
    required this.softBorder,
    required this.text,
    required this.muted,
    required this.accent,
    required this.accentPressed,
    required this.accentInk,
    required this.onAccent,
    required this.amber,
    required this.red,
  });

  static const dark = VoxColors(
    background: Color(0xFF121319),
    card: Color(0xFF1B1D27),
    raised: Color(0xFF22242F),
    border: Color(0xFF2B2E3B),
    softBorder: Color(0xFF242631),
    text: Color(0xFFECEEF4),
    muted: Color(0xFF8B8D9C),
    accent: Color(0xFF3ECF8E),
    accentPressed: Color(0xFF269E69),
    accentInk: Color(0xFF3ECF8E),
    onAccent: Color(0xFF0B2418),
    amber: Color(0xFFF0A54A),
    red: Color(0xFFF0546B),
  );

  static const light = VoxColors(
    background: Color(0xFFF3F4F7),
    card: Color(0xFFFFFFFF),
    raised: Color(0xFFE9ECF2),
    border: Color(0xFFDADDE6),
    softBorder: Color(0xFFE6E8EF),
    text: Color(0xFF14161C),
    muted: Color(0xFF5B5F6E),
    accent: Color(0xFF3ECF8E),
    accentPressed: Color(0xFF2DB77C),
    accentInk: Color(0xFF0F7A52),
    onAccent: Color(0xFF0B2418),
    amber: Color(0xFF94570A),
    red: Color(0xFFD4304A),
  );

  final Color background;
  final Color card;
  final Color raised;
  final Color border;
  final Color softBorder;
  final Color text;
  final Color muted;
  final Color accent;
  final Color accentPressed;
  final Color accentInk;
  final Color onAccent;
  final Color amber;
  final Color red;

  @override
  VoxColors copyWith({
    Color? background,
    Color? card,
    Color? raised,
    Color? border,
    Color? softBorder,
    Color? text,
    Color? muted,
    Color? accent,
    Color? accentPressed,
    Color? accentInk,
    Color? onAccent,
    Color? amber,
    Color? red,
  }) {
    return VoxColors(
      background: background ?? this.background,
      card: card ?? this.card,
      raised: raised ?? this.raised,
      border: border ?? this.border,
      softBorder: softBorder ?? this.softBorder,
      text: text ?? this.text,
      muted: muted ?? this.muted,
      accent: accent ?? this.accent,
      accentPressed: accentPressed ?? this.accentPressed,
      accentInk: accentInk ?? this.accentInk,
      onAccent: onAccent ?? this.onAccent,
      amber: amber ?? this.amber,
      red: red ?? this.red,
    );
  }

  @override
  VoxColors lerp(ThemeExtension<VoxColors>? other, double t) {
    if (other is! VoxColors) return this;
    return VoxColors(
      background: Color.lerp(background, other.background, t)!,
      card: Color.lerp(card, other.card, t)!,
      raised: Color.lerp(raised, other.raised, t)!,
      border: Color.lerp(border, other.border, t)!,
      softBorder: Color.lerp(softBorder, other.softBorder, t)!,
      text: Color.lerp(text, other.text, t)!,
      muted: Color.lerp(muted, other.muted, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentPressed: Color.lerp(accentPressed, other.accentPressed, t)!,
      accentInk: Color.lerp(accentInk, other.accentInk, t)!,
      onAccent: Color.lerp(onAccent, other.onAccent, t)!,
      amber: Color.lerp(amber, other.amber, t)!,
      red: Color.lerp(red, other.red, t)!,
    );
  }
}

extension VoxColorsContext on BuildContext {
  /// The active [VoxColors]. The theme always registers one.
  VoxColors get vox => Theme.of(this).extension<VoxColors>()!;
}
