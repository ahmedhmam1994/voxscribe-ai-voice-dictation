import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// Builds the app's [ThemeData] from the color tokens.
abstract final class AppTheme {
  static ThemeData get dark => _build(Brightness.dark, VoxColors.dark);
  static ThemeData get light => _build(Brightness.light, VoxColors.light);

  static ThemeData _build(Brightness brightness, VoxColors c) {
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Inter',
      brightness: brightness,
      scaffoldBackgroundColor: c.background,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: c.accent,
        onPrimary: c.onAccent,
        secondary: c.accentInk,
        onSecondary: c.background,
        error: c.red,
        onError: c.background,
        surface: c.card,
        onSurface: c.text,
      ),
      dividerColor: c.softBorder,
      textTheme: _textTheme(c),
      extensions: [c],
    );
  }

  /// Sizes follow the design brief: 12 labels, 13 meta, 15 list text,
  /// 17 body and transcript, 28 screen title, 52 hero number.
  static TextTheme _textTheme(VoxColors c) {
    return TextTheme(
      labelSmall: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.9,
        color: c.muted,
      ),
      bodySmall: TextStyle(fontSize: 13, color: c.muted),
      bodyMedium: TextStyle(fontSize: 15, height: 1.45, color: c.text),
      bodyLarge: TextStyle(fontSize: 17, height: 1.5, color: c.text),
      titleLarge: TextStyle(
        fontSize: 28,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
        color: c.text,
      ),
      displayMedium: TextStyle(
        fontSize: 52,
        fontWeight: FontWeight.w800,
        letterSpacing: -1.5,
        color: c.text,
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
    );
  }
}
