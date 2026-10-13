/// Design-system cards (§52): DrugCard, ProductCard, SystemCard, SourceCard.
import 'package:flutter/material.dart';

import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../models/models.dart';
import 'common.dart';

class DrugCard extends StatelessWidget {
  const DrugCard({super.key, required this.nameEn, required this.nameAr, required this.subtitle,
    this.verificationStatus = 'draft', this.isDemo = false, this.onTap});

  final String nameEn;
  final String nameAr;
  final String subtitle;
  final String verificationStatus;
  final bool isDemo;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AphSpacing.md),
          child: Row(
            children: [
              Container(
                width: 42, height: 42,
                decoration: BoxDecoration(
                  color: AphColors.cyan.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.medication_outlined, color: AphColors.cyan),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Flexible(child: Text(nameEn, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15))),
                      if (isDemo) ...[
                        const SizedBox(width: 6),
                        const DemoBadge(),
                      ],
                    ]),
                    if (nameAr.isNotEmpty)
                      Text(nameAr, textDirection: TextDirection.rtl,
                          style: const TextStyle(color: AphColors.textSecondary, fontSize: 13)),
                    if (subtitle.isNotEmpty)
                      Text(subtitle, style: const TextStyle(color: AphColors.textSecondary, fontSize: 12)),
                  ],
                ),
              ),
              VerificationBadge(status: verificationStatus, compact: true),
              const Icon(Icons.chevron_right, color: AphColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}

class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.nameEn, required this.nameAr, required this.details,
    this.verificationStatus = 'draft', this.isDemo = false, this.onTap});

  final String nameEn;
  final String nameAr;
  final String details;
  final String verificationStatus;
  final bool isDemo;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AphSpacing.md),
          child: Row(children: [
            Container(
              width: 42, height: 42,
              decoration: BoxDecoration(
                color: AphColors.emerald.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.inventory_2_outlined, color: AphColors.emerald),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Flexible(child: Text(nameEn, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15))),
                  if (isDemo) ...[const SizedBox(width: 6), const DemoBadge()],
                ]),
                if (nameAr.isNotEmpty)
                  Text(nameAr, textDirection: TextDirection.rtl,
                      style: const TextStyle(color: AphColors.textSecondary, fontSize: 13)),
                Text(details, style: const TextStyle(color: AphColors.textSecondary, fontSize: 12)),
              ]),
            ),
            VerificationBadge(status: verificationStatus, compact: true),
          ]),
        ),
      ),
    );
  }
}

class SystemCard extends StatelessWidget {
  const SystemCard({super.key, required this.nameEn, required this.nameAr,
    required this.drugCount, this.onTap});

  final String nameEn;
  final String nameAr;
  final int drugCount;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  color: AphColors.navy.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: const Icon(Icons.monitor_heart_outlined, size: 20, color: AphColors.navy),
              ),
              const Spacer(),
              Text(nameEn,
                  maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              Text(nameAr, textDirection: TextDirection.rtl, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: AphColors.textSecondary, fontSize: 11)),
              const SizedBox(height: 4),
              Text('$drugCount ${t.tr('products')}',
                  style: const TextStyle(color: AphColors.cyan, fontSize: 11, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}

class SourceCard extends StatelessWidget {
  const SourceCard({super.key, required this.name, this.url, this.section, this.sourceType});

  final String name;
  final String? url;
  final String? section;
  final String? sourceType;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AphColors.border),
        borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
      ),
      child: Row(children: [
        const Icon(Icons.menu_book_outlined, size: 18, color: AphColors.cyan),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
            if (section != null && section!.isNotEmpty)
              Text(section!, style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
          ]),
        ),
        if (url != null && url!.isNotEmpty)
          const Icon(Icons.open_in_new, size: 14, color: AphColors.textSecondary),
      ]),
    );
  }
}
