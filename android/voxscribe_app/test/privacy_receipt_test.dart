import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voxscribe_app/app/theme/app_theme.dart';
import 'package:voxscribe_app/features/privacy/network_log.dart';
import 'package:voxscribe_app/features/privacy/privacy_receipt_page.dart';

class _FakeNetworkLog implements NetworkLog {
  _FakeNetworkLog(this.list);

  final List<NetworkLogEntry> list;

  @override
  Future<List<NetworkLogEntry>> entries() async => list;
}

Widget _page(NetworkLog log) => MaterialApp(
  theme: AppTheme.dark,
  home: PrivacyReceiptPage(log: log),
);

void main() {
  testWidgets('lists each request with where it went and what was sent', (
    tester,
  ) async {
    await tester.pumpWidget(
      _page(
        _FakeNetworkLog([
          NetworkLogEntry(
            at: DateTime(2026, 11, 1, 14, 5),
            what: 'Update check',
            host: 'api.github.com',
            sent: 'Nothing about you: a request for the list of releases',
          ),
        ]),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Never sent'), findsOneWidget);
    expect(find.text('Update check'), findsOneWidget);
    expect(find.text('To api.github.com'), findsOneWidget);
    expect(find.text('1 Nov 2026, 14:05'), findsOneWidget);
  });

  testWidgets('says so when VoxScribe has not gone online', (tester) async {
    await tester.pumpWidget(_page(_FakeNetworkLog(const [])));
    await tester.pumpAndSettle();
    expect(find.textContaining('Nothing yet'), findsOneWidget);
  });
}
