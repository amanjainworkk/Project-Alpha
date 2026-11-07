// Project Alpha Mobile Living Canvas & Command Center
// Design System: OLED Dark Mode ThemeData Configuration
// Master Design Spec §11.3 & CDO Job Description §4

import 'package:flutter/material.dart';
import 'alpha_colors.dart';

/// Project Alpha Master Theme Configuration.
/// Calibrated for OLED screens with battery-saving pure blacks (#0A0A0F) and
/// vibrant electric cyan (#06B6D4) and blue (#3B82F6) interactive accents.
class AlphaTheme {
  AlphaTheme._();

  /// Primary Dark ThemeData for Project Alpha Mobile APK.
  static ThemeData get darkTheme {
    final baseColorScheme = const ColorScheme.dark(
      brightness: Brightness.dark,
      primary: AlphaColors.primaryCyan,
      onPrimary: AlphaColors.backgroundOled,
      primaryContainer: Color(0xFF0E3A42),
      onPrimaryContainer: AlphaColors.primaryCyanNeon,
      secondary: AlphaColors.secondaryBlue,
      onSecondary: AlphaColors.textPrimary,
      secondaryContainer: Color(0xFF1E3A5F),
      onSecondaryContainer: AlphaColors.textPrimary,
      tertiary: AlphaColors.accentPurple,
      onTertiary: AlphaColors.textPrimary,
      error: AlphaColors.errorRose,
      onError: AlphaColors.textPrimary,
      surface: AlphaColors.surfaceLevel1,
      onSurface: AlphaColors.textPrimary,
      surfaceContainer: AlphaColors.surfaceLevel2,
      surfaceContainerHigh: AlphaColors.surfaceLevel3,
      outline: AlphaColors.border,
      outlineVariant: AlphaColors.borderSubtle,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AlphaColors.backgroundOled,
      canvasColor: AlphaColors.backgroundOled,
      cardColor: AlphaColors.surfaceLevel2,
      dividerColor: AlphaColors.border,
      primaryColor: AlphaColors.primaryCyan,
      colorScheme: baseColorScheme,

      // -----------------------------------------------------------------------
      // Typography
      // -----------------------------------------------------------------------
      textTheme: const TextTheme(
        displayLarge: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 32,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.5,
        ),
        displayMedium: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 28,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.5,
        ),
        headlineLarge: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 24,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.3,
        ),
        headlineMedium: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.2,
        ),
        headlineSmall: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
        titleLarge: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
        titleMedium: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        titleSmall: TextStyle(
          color: AlphaColors.textSecondary,
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
        bodyLarge: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.normal,
          height: 1.5,
        ),
        bodyMedium: TextStyle(
          color: AlphaColors.textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.normal,
          height: 1.4,
        ),
        bodySmall: TextStyle(
          color: AlphaColors.textMuted,
          fontSize: 12,
          fontWeight: FontWeight.normal,
          height: 1.3,
        ),
        labelLarge: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.2,
        ),
        labelMedium: TextStyle(
          color: AlphaColors.textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
        labelSmall: TextStyle(
          color: AlphaColors.textMuted,
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.1,
        ),
      ),

      // -----------------------------------------------------------------------
      // App Bar Theme
      // -----------------------------------------------------------------------
      appBarTheme: const AppBarTheme(
        backgroundColor: AlphaColors.surfaceLevel1,
        foregroundColor: AlphaColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.2,
        ),
        iconTheme: IconThemeData(
          color: AlphaColors.textPrimary,
        ),
        actionsIconTheme: IconThemeData(
          color: AlphaColors.primaryCyan,
        ),
      ),

      // -----------------------------------------------------------------------
      // Card Theme
      // -----------------------------------------------------------------------
      cardTheme: CardTheme(
        color: AlphaColors.surfaceLevel2,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AlphaColors.border, width: 1.0),
        ),
        margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      ),

      // -----------------------------------------------------------------------
      // Elevated Button Theme
      // -----------------------------------------------------------------------
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AlphaColors.primaryCyan,
          foregroundColor: AlphaColors.backgroundOled,
          elevation: 2,
          shadowColor: AlphaColors.primaryCyanGlow,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            letterSpacing: 0.3,
          ),
        ),
      ),

      // -----------------------------------------------------------------------
      // Outlined Button Theme
      // -----------------------------------------------------------------------
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AlphaColors.primaryCyan,
          side: const BorderSide(color: AlphaColors.primaryCyan, width: 1.5),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),

      // -----------------------------------------------------------------------
      // Text Button Theme
      // -----------------------------------------------------------------------
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AlphaColors.primaryCyan,
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),

      // -----------------------------------------------------------------------
      // Input Decoration Theme
      // -----------------------------------------------------------------------
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AlphaColors.surfaceLevel1,
        hintStyle: const TextStyle(color: AlphaColors.textMuted, fontSize: 14),
        labelStyle: const TextStyle(color: AlphaColors.textSecondary, fontSize: 14),
        prefixIconColor: AlphaColors.primaryCyan,
        suffixIconColor: AlphaColors.textSecondary,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AlphaColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AlphaColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AlphaColors.primaryCyan, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AlphaColors.errorRose, width: 1.5),
        ),
      ),

      // -----------------------------------------------------------------------
      // Bottom Navigation Bar Theme
      // -----------------------------------------------------------------------
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AlphaColors.surfaceLevel1,
        selectedItemColor: AlphaColors.primaryCyan,
        unselectedItemColor: AlphaColors.textMuted,
        selectedLabelStyle: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
        unselectedLabelStyle: TextStyle(fontSize: 12),
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),

      // -----------------------------------------------------------------------
      // Tab Bar Theme
      // -----------------------------------------------------------------------
      tabBarTheme: const TabBarTheme(
        indicatorColor: AlphaColors.primaryCyan,
        labelColor: AlphaColors.primaryCyan,
        unselectedLabelColor: AlphaColors.textSecondary,
        dividerColor: AlphaColors.border,
      ),

      // -----------------------------------------------------------------------
      // Progress Indicators
      // -----------------------------------------------------------------------
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AlphaColors.primaryCyan,
        linearTrackColor: AlphaColors.borderSubtle,
        circularTrackColor: AlphaColors.borderSubtle,
      ),

      // -----------------------------------------------------------------------
      // Dialog & SnackBar Themes
      // -----------------------------------------------------------------------
      dialogTheme: DialogTheme(
        backgroundColor: AlphaColors.surfaceLevel1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AlphaColors.border),
        ),
        titleTextStyle: const TextStyle(
          color: AlphaColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
        contentTextStyle: const TextStyle(
          color: AlphaColors.textSecondary,
          fontSize: 14,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AlphaColors.surfaceLevel2,
        contentTextStyle: const TextStyle(color: AlphaColors.textPrimary),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: AlphaColors.border),
        ),
        behavior: SnackBarBehavior.floating,
      ),

      // -----------------------------------------------------------------------
      // Divider Theme
      // -----------------------------------------------------------------------
      dividerTheme: const DividerThemeData(
        color: AlphaColors.border,
        thickness: 1,
        space: 1,
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Custom Typography Helpers
  // ---------------------------------------------------------------------------

  /// Tabular Monospace font style for token metrics, latencies, and telemetry.
  static const TextStyle monoStyle = TextStyle(
    fontFamily: 'Courier',
    fontSize: 13,
    color: AlphaColors.textSecondary,
    letterSpacing: -0.2,
  );

  /// Micro status pill label style (e.g., 'RUNNING', 'AUDITING', 'DONE').
  static TextStyle statusPillStyle(Color color) => TextStyle(
        color: color,
        fontSize: 11,
        fontWeight: FontWeight.bold,
        letterSpacing: 0.5,
      );
}
