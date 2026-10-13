/// Sync-queue semantics tests (§32–§33): enqueue, retry, conflict surfacing.
/// These mirror the on-device SQLite sync_queue behaviour.
import 'package:flutter_test/flutter_test.dart';

/// Lightweight in-memory replica of the local sync_queue table semantics
/// (kept dependency-free so the test runs without sqflite platform channels).
class FakeSyncQueue {
  final List<Map<String, dynamic>> items = [];

  void enqueue({
    required String entityType,
    required String entityId,
    required String operation,
    int localVersion = 0,
    int serverVersion = 0,
  }) {
    items.add({
      'id': items.length + 1,
      'entity_type': entityType,
      'entity_id': entityId,
      'operation': operation,
      'local_version': localVersion,
      'server_version': serverVersion,
      'status': 'pending',
      'retry_count': 0,
    });
  }

  List<Map<String, dynamic>> pending() =>
      items.where((i) => i['status'] == 'pending').toList();

  void mark(int id, String status) {
    final item = items.firstWhere((i) => i['id'] == id);
    item['status'] = status;
    if (status == 'failed') item['retry_count'] = (item['retry_count'] as int) + 1;
  }

  /// Conflict rule (§32): if the server record moved past the client's
  /// base version, the change is CONFLICT — never overwritten blindly.
  bool wouldConflict(int serverRecordVersion, int baseVersion) =>
      serverRecordVersion > baseVersion;
}

void main() {
  group('sync queue', () {
    test('operations are queued in order and marked completed', () {
      final q = FakeSyncQueue();
      q.enqueue(entityType: 'favorite', entityId: 'd1', operation: 'favorite_add');
      q.enqueue(entityType: 'drug', entityId: 'd2', operation: 'update', localVersion: 3);
      expect(q.pending().length, 2);
      q.mark(1, 'completed');
      expect(q.pending().length, 1);
    });

    test('failed items keep retry state (§32 retry)', () {
      final q = FakeSyncQueue();
      q.enqueue(entityType: 'drug', entityId: 'd1', operation: 'update');
      q.mark(1, 'failed');
      q.mark(1, 'failed');
      expect(q.items.first['retry_count'], 2);
    });

    test('stale base versions surface conflicts instead of overwriting', () {
      final q = FakeSyncQueue();
      // server already at version 3, client based its edit on version 1
      expect(q.wouldConflict(3, 1), isTrue);
      // client knew the latest version
      expect(q.wouldConflict(3, 3), isFalse);
      // client base is unknown (0) and the record exists on the server → conflict
      expect(q.wouldConflict(1, 0), isTrue);
    });
  });
}
