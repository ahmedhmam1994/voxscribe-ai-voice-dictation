import 'package:flutter/material.dart';
import 'package:voxscribe_app/app/theme/vox_colors.dart';
import 'package:voxscribe_app/shared/widgets/section_label.dart';

/// A labelled card holding a list of setting rows separated by thin lines.
class SettingsGroup extends StatelessWidget {
  const SettingsGroup({required this.label, required this.children, super.key});

  final String label;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionLabel(label),
        Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: c.card,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: c.border),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (var i = 0; i < children.length; i++) ...[
                if (i > 0)
                  Divider(height: 1, thickness: 1, color: c.softBorder),
                children[i],
              ],
            ],
          ),
        ),
      ],
    );
  }
}

/// One tappable row: a title, an optional line under it and a trailing widget.
class SettingsRow extends StatelessWidget {
  const SettingsRow({
    required this.title,
    this.subtitle,
    this.trailing,
    this.titleColor,
    this.onTap,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Color? titleColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    final theme = Theme.of(context).textTheme;
    final line = subtitle;
    return InkWell(
      onTap: onTap,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 60),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.bodyLarge?.copyWith(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: titleColor ?? c.text,
                      ),
                    ),
                    if (line != null) ...[
                      const SizedBox(height: 2),
                      Text(line, style: theme.bodySmall),
                    ],
                  ],
                ),
              ),
              if (trailing case final widget?) ...[
                const SizedBox(width: 12),
                widget,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A row with an on/off switch.
class SettingsSwitchRow extends StatelessWidget {
  const SettingsSwitchRow({
    required this.title,
    required this.value,
    required this.onChanged,
    this.subtitle,
    super.key,
  });

  final String title;
  final String? subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.vox;
    return Semantics(
      toggled: value,
      label: title,
      child: SettingsRow(
        title: title,
        subtitle: subtitle,
        onTap: () => onChanged(!value),
        trailing: ExcludeSemantics(
          child: Switch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: c.onAccent,
            activeTrackColor: c.accentInk,
          ),
        ),
      ),
    );
  }
}
