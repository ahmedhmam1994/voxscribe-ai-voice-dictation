import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// The four-bar VoxScribe mark.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key});

  static const _heights = [8.0, 16.0, 20.0, 12.0];

  @override
  Widget build(BuildContext context) {
    final color = context.vox.accentInk;
    return ExcludeSemantics(
      child: SizedBox(
        height: 20,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final height in _heights)
              Container(
                width: 3,
                height: height,
                margin: const EdgeInsets.symmetric(horizontal: 1),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
