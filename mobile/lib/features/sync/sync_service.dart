/// Synchronization engine client (§30–§33).
///
/// Incremental pull by watermark; local changes travel through the on-device
/// `sync_queue` with retry + conflict surfacing. Never overwrites newer
/// server data blindly — conflicts are reported for client-side resolution.
import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../../core/database/local_database.dart';
import '../../core/network/api_client.dart';

enum SyncPhase { idle, pulling, pushing, done, failed }

class SyncService {
  SyncService({ApiClient? api, LocalDatabase? db})
      : _api = api ?? ApiClient(),
        _db = db ?? LocalDatabase.instance;

  final ApiClient _api;
  final LocalDatabase _db;

  String deviceId = 'flutter-default';

  Future<SyncResult> sync({String datasetMode = 'essential', List<String> systemIds = const []}) async {
    final state = await _db.syncState();
    final since = state?['last_synced_at'] as String?;
    int pulled = 0;
    int pushed = 0;
    int conflicts = 0;
    String? error;

    try {
      // ---- pull ---------------------------------------------------------
      await _db.setSyncState(status: 'pulling');
      for (final entity in ['drug', 'product']) {
        bool hasMore = true;
        String? watermark = since;
        while (hasMore) {
          final page = await _api.post('/sync/pull', body: {
            'device_id': deviceId,
            'entity_type': entity,
            if (watermark != null) 'since': watermark,
            if (systemIds.isNotEmpty) 'system_ids': systemIds,
            'limit': 200,
          });
          final items = page['items'] as List;
          pulled += items.length;
          await _storePulled(entity, items);
          hasMore = page['has_more'] as bool? ?? false;
          if (items.isNotEmpty) {
            watermark = items.last['updated_at'] as String?;
          }
          if (!hasMore) break;
        }
      }

      // ---- push local queue --------------------------------------------
      await _db.setSyncState(status: 'pushing');
      final pending = await _db.pendingSyncItems();
      if (pending.isNotEmpty) {
        final changes = pending
            .map((row) => {
                  'entity_type': row['entity_type'],
                  'entity_id': row['entity_id'],
                  'operation': row['operation'],
                  'payload': row['payload'],
                  'local_version': row['local_version'],
                  'base_version': row['server_version'],
                })
            .toList();
        final result = await _api.post('/sync/push', body: {'device_id': deviceId, 'changes': changes});
        pushed = result['accepted'] as int? ?? 0;
        conflicts = result['conflicts'] as int? ?? 0;
        for (final row in pending) {
          await _db.markSyncItem(row['id'] as int, 'completed');
        }
      }

      await _db.setSyncState(
        lastSyncedAt: DateTime.now().toUtc().toIso8601String(),
        status: conflicts > 0 ? 'conflict' : 'completed',
        datasetMode: datasetMode,
        lastError: '',
      );
    } catch (e) {
      error = e.toString();
      await _db.setSyncState(status: 'failed', lastError: error);
      // failed items stay queued for retry (§32)
    }

    return SyncResult(pulled: pulled, pushed: pushed, conflicts: conflicts, error: error);
  }

  Future<void> _storePulled(String entity, List<dynamic> items) async {
    final db = await _db.database;
    for (final raw in items) {
      final m = Map<String, dynamic>.from(raw as Map);
      if (entity == 'drug') {
        await db.insert('drugs', {
          'id': m['id'],
          'generic_name_en': m['generic_name_en'] ?? '',
          'generic_name_ar': m['generic_name_ar'] ?? '',
          'scientific_name': m['scientific_name'] ?? '',
          'drug_class': m['drug_class'] ?? '',
          'pharmacological_class_name': m['pharmacological_class_name'] ?? '',
          'atc_code': m['atc_code'] ?? '',
          'overview_en': m['overview_en'] ?? '',
          'overview_ar': m['overview_ar'] ?? '',
          'mechanism_en': m['mechanism_en'] ?? '',
          'mechanism_ar': m['mechanism_ar'] ?? '',
          'verification_status': m['verification_status'] ?? 'draft',
          'is_demo': (m['is_demo'] == true) ? 1 : 0,
          'record_version': m['record_version'] ?? 1,
          'updated_at': m['updated_at'] ?? '',
          'search_text': (m['generic_name_en'] ?? '').toString().toLowerCase(),
          'search_text_ar': (m['generic_name_ar'] ?? '').toString(),
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      } else {
        await db.insert('products', {
          'id': m['id'],
          'drug_id': m['drug_id'],
          'brand_name_en': m['brand_name_en'] ?? '',
          'brand_name_ar': m['brand_name_ar'] ?? '',
          'strength': m['strength'] ?? '',
          'dosage_form': m['dosage_form'] ?? '',
          'route': m['route'] ?? '',
          'barcode': m['barcode'] ?? '',
          'registration_number': m['registration_number'] ?? '',
          'verification_status': m['verification_status'] ?? 'draft',
          'is_demo': (m['is_demo'] == true) ? 1 : 0,
          'record_version': m['record_version'] ?? 1,
          'updated_at': m['updated_at'] ?? '',
          'search_text': (m['brand_name_en'] ?? '').toString().toLowerCase(),
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      }
    }
  }
}

class SyncResult {
  const SyncResult({required this.pulled, required this.pushed, required this.conflicts, this.error});
  final int pulled;
  final int pushed;
  final int conflicts;
  final String? error;

  bool get ok => error == null;
}
