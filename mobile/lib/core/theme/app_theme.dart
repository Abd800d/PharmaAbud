/// APH design tokens — medical navy / white / cyan / emerald (§2, §52).
import 'package:flutter/material.dart';

abstract class AphColors {
  static const navy = Color(0xFF0B2545);
  static const navyLight = Color(0xFF12335C);
  static const cyan = Color(0xFF0E7490);
  static const cyanAccent = Color(0xFF22D3EE);
  static const emerald = Color(0xFF059669);
  static const amber = Color(0xFFD97706);
  static const red = Color(0xFFDC2626);

  static const bg = Color(0xFFF5F7FA);
  static const surface = Colors.white;
  static const border = Color(0xFFE5E7EB);
  static const textPrimary = Color(0xFF111827);
  static const textSecondary = Color(0xFF6B7280);

  // dark theme
  static const darkBg = Color(0xFF0D1B2A);
  static const darkSurface = Color(0xFF13253B);
  static const darkBorder = Color(0xFF24405F);
}

abstract class AphSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double radius = 12;
  static const double radiusSm = 8;
}

abstract class AphTypography {
  static const String? arabicFontFamily = null; // system Arabic (Noto/Naskh)
  static const String latinFontFamily = 'Roboto';

  static TextTheme textTheme(TextTheme base) => base.copyWith(
        headlineSmall: base.headlineSmall?.copyWith(
          fontWeight: FontWeight.w800,
          color: AphColors.navy,
          letterSpacing: -0.3,
        ),
        titleLarge: base.titleLarge?.copyWith(
          fontWeight: FontWeight.w700,
          color: AphColors.navy,
        ),
        titleMedium: base.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: AphColors.textPrimary,
        ),
        bodyMedium: base.bodyMedium?.copyWith(
          color: AphColors.textPrimary,
          height: 1.45,
        ),
        bodySmall: base.bodySmall?.copyWith(color: AphColors.textSecondary),
        labelLarge: base.labelLarge?.copyWith(fontWeight: FontWeight.w600),
      );
}

ThemeData buildAphTheme({required Brightness brightness}) {
  final isDark = brightness == Brightness.dark;
  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AphColors.cyan,
      primary: isDark ? AphColors.cyanAccent : AphColors.cyan,
      secondary: AphColors.emerald,
      surface: isDark ? AphColors.darkSurface : AphColors.surface,
      error: AphColors.red,
      brightness: brightness,
    ),
    scaffoldBackgroundColor: isDark ? AphColors.darkBg : AphColors.bg,
  );
  return base.copyWith(
    textTheme: AphTypography.textTheme(base.textTheme),
    appBarTheme: AppBarTheme(
      backgroundColor: isDark ? AphColors.darkSurface : AphColors.surface,
      foregroundColor: isDark ? Colors.white : AphColors.navy,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: isDark ? Colors.white : AphColors.navy,
      ),
    ),
    cardTheme: CardThemeData(
      color: isDark ? AphColors.darkSurface : AphColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        side: BorderSide(color: isDark ? AphColors.darkBorder : AphColors.border),
      ),
      margin: EdgeInsets.zero,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: isDark ? AphColors.darkSurface : AphColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
        borderSide: BorderSide(color: isDark ? AphColors.darkBorder : AphColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
        borderSide: BorderSide(color: isDark ? AphColors.darkBorder : AphColors.border),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AphSpacing.radiusSm)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600),
      ),
    ),
    dividerTheme: DividerThemeData(
      color: isDark ? AphColors.darkBorder : AphColors.border,
      thickness: 1,
    ),
  );
}
