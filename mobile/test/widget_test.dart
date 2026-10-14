/// App smoke widget tests (§98).
///
/// This file intentionally exists so that `flutter create` (run in CI to
/// generate the Android scaffolding) does NOT inject its default counter
/// smoke test — which would fail against the real APH app.
///
/// Pure widgets only: no sqflite / network / platform channels, so
/// `flutter test` runs on CI without an emulator.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'package:aph_mobile/core/localization/app_localizations.dart';
import 'package:aph_mobile/shared/widgets/states.dart';

Widget _harness(Widget child, {Locale locale = const Locale('en')}) {
  return MaterialApp(
    locale: locale,
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    home: Scaffold(body: child),
  );
}

void main() {
  testWidgets('EmptyState renders message and icon', (WidgetTester tester) async {
    await tester.pumpWidget(_harness(const EmptyState(message: 'No matching drug was found.')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('No matching drug was found.'), findsOneWidget);
    expect(find.byIcon(Icons.search_off), findsOneWidget);
  });

  testWidgets('ErrorState surfaces message and retry action', (WidgetTester tester) async {
    var tapped = 0;
    await tester.pumpWidget(_harness(ErrorState(
      message: 'Network error — please check your connection.',
      onRetry: () => tapped++,
    )));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Network error — please check your connection.'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
    await tester.tap(find.byType(FilledButton));
    expect(tapped, 1);
  });

  testWidgets('LoadingSkeleton renders without platform channels', (WidgetTester tester) async {
    await tester.pumpWidget(_harness(const LoadingSkeleton(lines: 2)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(LoadingSkeleton), findsOneWidget);
    expect(find.byType(Card), findsWidgets);
  });

  testWidgets('Arabic localization resolves RTL strings', (WidgetTester tester) async {
    await tester.pumpWidget(_harness(
      const EmptyState(message: 'لم يتم العثور على دواء مطابق.'),
      locale: const Locale('ar'),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('لم يتم العثور على دواء مطابق.'), findsOneWidget);
    final BuildContext ctx = tester.element(find.byType(EmptyState));
    expect(AppLocalizations.of(ctx).isArabic, isTrue);
  });
}
