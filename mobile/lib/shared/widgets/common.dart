/// Shared chrome widgets (§52): AppHeader, VerificationBadge, DemoBadge,
/// AphSearchBar, SyncStatusChip, BottomNavigation.
import 'package:flutter/material.dart';

import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';

class AppHeader extends StatelessWidget implements PreferredSizeWidget {
  const AppHeader({super.key, this.title, this.showBrand = true, this.actions = const []});

  final String? title;
  final bool showBrand;
  final List<Widget> actions;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return AppBar(
      title: showBrand
          ? Row(children: [
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(
                  color: AphColors.navy,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Center(
                  child: Text('APH',
                      style: TextStyle(color: AphColors.cyanAccent, fontSize: 10, fontWeight: FontWeight.w800)),
                ),
              ),
              const SizedBox(width: 10),
              Flexible(
                child: Text(title ?? t.tr('appTitle'),
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              ),
            ])
          : Text(title ?? ''),
      actions: actions,
    );
  }
}

class VerificationBadge extends StatelessWidget {
  const VerificationBadge({super.key, required this.status, this.compact = false});

  final String status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final (label, color) = switch (status) {
      'verified' => (t.tr('verified'), AphColors.emerald),
      'pending_verification' => (t.tr('pendingVerification'), AphColors.amber),
      'imported_pending_review' => (t.tr('importedPendingReview'), AphColors.amber),
      'needs_update' => (t.tr('needsUpdate'), AphColors.amber),
      'rejected' => (t.tr('rejected'), AphColors.red),
      'archived' => (t.tr('archived'), AphColors.textSecondary),
      _ => (t.tr('draft'), AphColors.textSecondary),
    };
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 12, vertical: compact ? 3 : 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        compact && status == 'imported_pending_review' ? '•••' : label,
        style: TextStyle(
          color: color,
          fontSize: compact ? 10 : 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class DemoBadge extends StatelessWidget {
  const DemoBadge({super.key});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AphColors.amber.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(t.tr('demoData'),
          style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AphColors.amber)),
    );
  }
}

class AphSearchBar extends StatelessWidget {
  const AphSearchBar({super.key, this.controller, this.hint, this.onChanged, this.onSubmitted,
    this.onScanTap, this.showScan = true});

  final TextEditingController? controller;
  final String? hint;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final VoidCallback? onScanTap;
  final bool showScan;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Container(
      decoration: BoxDecoration(
        color: AphColors.surface,
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        border: Border.all(color: AphColors.border),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 8, offset: const Offset(0, 2))],
      ),
      child: Row(children: [
        const Padding(padding: EdgeInsets.only(left: 12), child: Icon(Icons.search, color: AphColors.textSecondary)),
        Expanded(
          child: TextField(
            controller: controller,
            onChanged: onChanged,
            onSubmitted: onSubmitted,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              hintText: hint ?? t.tr('searchHint'),
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              fillColor: Colors.transparent,
            ),
          ),
        ),
        if (showScan)
          IconButton(
            onPressed: onScanTap,
            icon: const Icon(Icons.qr_code_scanner, color: AphColors.cyan),
            tooltip: t.tr('scanDrug'),
          ),
      ]),
    );
  }
}

class SyncStatusChip extends StatelessWidget {
  const SyncStatusChip({super.key, required this.isOnline, this.lastSync, this.syncing = false, this.onTap});

  final bool isOnline;
  final String? lastSync;
  final bool syncing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final color = !isOnline ? AphColors.amber : syncing ? AphColors.cyan : AphColors.emerald;
    final label = syncing
        ? t.tr('syncing')
        : isOnline
            ? t.tr('online')
            : t.tr('offline');
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(isOnline ? Icons.cloud_done_outlined : Icons.cloud_off, size: 13, color: color),
          const SizedBox(width: 5),
          Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: color)),
        ]),
      ),
    );
  }
}
