import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';

/// A bordered surface used for the main content blocks.
class VoxCard extends StatelessWidget {
  const VoxCard({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.border),
      ),
      child: child,
    );
  }
}
