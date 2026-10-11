import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// WCAG contrast ratio between two opaque colors.
double _contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  final lighter = la > lb ? la : lb;
  final darker = la > lb ? lb : la;
  return (lighter + 0.05) / (darker + 0.05);
}

void main() {
  const minTextContrast = 4.5;

  for (final entry in {
    'dark': VoxColors.dark,
    'light': VoxColors.light,
  }.entries) {
    final c = entry.value;

    group('${entry.key} theme contrast', () {
      test('main text is readable on background and cards', () {
        expect(
          _contrast(c.text, c.background),
          greaterThanOrEqualTo(minTextContrast),
        );
        expect(
          _contrast(c.text, c.card),
          greaterThanOrEqualTo(minTextContrast),
        );
      });

      test('muted text is readable on background and cards', () {
        expect(
          _contrast(c.muted, c.background),
          greaterThanOrEqualTo(minTextContrast),
        );
        expect(
          _contrast(c.muted, c.card),
          greaterThanOrEqualTo(minTextContrast),
        );
      });

      test('accent used as text or icon is readable', () {
        expect(
          _contrast(c.accentInk, c.background),
          greaterThanOrEqualTo(minTextContrast),
        );
        expect(
          _contrast(c.accentInk, c.card),
          greaterThanOrEqualTo(minTextContrast),
        );
      });

      test('text on the accent fill is readable', () {
        expect(
          _contrast(c.onAccent, c.accent),
          greaterThanOrEqualTo(minTextContrast),
        );
        expect(
          _contrast(c.onAccent, c.accentPressed),
          greaterThanOrEqualTo(minTextContrast),
        );
      });

      test('status colors are readable on cards', () {
        expect(
          _contrast(c.amber, c.card),
          greaterThanOrEqualTo(minTextContrast),
        );
        expect(_contrast(c.red, c.card), greaterThanOrEqualTo(minTextContrast));
      });
    });
  }

  test('lerp at the ends returns each side', () {
    expect(
      VoxColors.dark.lerp(VoxColors.light, 0).background,
      VoxColors.dark.background,
    );
    expect(
      VoxColors.dark.lerp(VoxColors.light, 1).background,
      VoxColors.light.background,
    );
  });
}
