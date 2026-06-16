import 'package:flutter/material.dart';

// ── Gerald brand palette ──────────────────────────────────────────────────────
const kBgColor      = Color(0xFF050509);   // Near-black background
const kSurfaceColor = Color(0xFF0C0C1A);   // Primary surface
const kSurface2     = Color(0xFF111126);   // Elevated surface
const kBorderColor  = Color(0xFF1C1C38);   // Subtle border

const kAccentBlue   = Color(0xFF2979FF);   // Electric blue — primary accent
const kAccentGreen  = Color(0xFF00E676);   // Bright green — success/Gerald
const kAccentPurple = Color(0xFF9C27B0);   // Purple — speaking state

const kTextPrimary   = Color(0xFFECECFF);  // Near-white text
const kTextSecondary = Color(0xFF555578);  // Secondary/muted text
const kTextMuted     = Color(0xFF2E2E48);  // Very muted text

const kUserBubble   = Color(0xFF091530);   // User message bubble
const kGeraldBubble = Color(0xFF071410);   // Gerald message bubble

const kStatusIdle      = Color(0xFF3E3E62);
const kStatusPlanning  = Color(0xFF2979FF);
const kStatusAwaiting  = Color(0xFFFFB300);
const kStatusExecuting = Color(0xFF00E676);
const kStatusError     = Color(0xFFFF3B5C);
const kStatusSpeaking  = Color(0xFF9C27B0);

// ── Theme ─────────────────────────────────────────────────────────────────────
final geraldDarkTheme = ThemeData(
  brightness: Brightness.dark,
  colorScheme: const ColorScheme.dark(
    primary: kAccentBlue,
    secondary: kAccentGreen,
    surface: kSurfaceColor,
    error: kStatusError,
    onPrimary: Colors.white,
    onSecondary: Colors.black,
    onSurface: kTextPrimary,
  ),
  scaffoldBackgroundColor: kBgColor,
  appBarTheme: const AppBarTheme(
    backgroundColor: kBgColor,
    foregroundColor: kTextPrimary,
    elevation: 0,
    scrolledUnderElevation: 0,
    titleSpacing: 0,
    titleTextStyle: TextStyle(
      color: kTextPrimary,
      fontSize: 16,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.3,
    ),
  ),
  cardTheme: CardThemeData(
    color: kSurfaceColor,
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(14),
      side: const BorderSide(color: kBorderColor),
    ),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: kAccentBlue,
      foregroundColor: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      textStyle: const TextStyle(
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
        fontSize: 13,
      ),
    ),
  ),
  textButtonTheme: TextButtonThemeData(
    style: TextButton.styleFrom(foregroundColor: kAccentBlue),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: kSurface2,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: const BorderSide(color: kBorderColor),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: const BorderSide(color: kBorderColor),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: const BorderSide(color: kAccentBlue, width: 1.5),
    ),
    hintStyle: const TextStyle(color: kTextSecondary),
    labelStyle: const TextStyle(color: kTextSecondary),
    helperStyle: const TextStyle(color: kTextSecondary, fontSize: 12),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
  ),
  switchTheme: SwitchThemeData(
    thumbColor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.selected) ? kAccentBlue : kTextSecondary,
    ),
    trackColor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.selected)
          ? kAccentBlue.withOpacity(0.35)
          : kBorderColor,
    ),
  ),
  dividerTheme: const DividerThemeData(color: kBorderColor, thickness: 1),
  listTileTheme: const ListTileThemeData(
    iconColor: kTextSecondary,
    textColor: kTextPrimary,
  ),
  dialogTheme: DialogThemeData(
    backgroundColor: kSurface2,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
  ),
  snackBarTheme: SnackBarThemeData(
    backgroundColor: kSurface2,
    contentTextStyle: const TextStyle(color: kTextPrimary),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
    behavior: SnackBarBehavior.floating,
  ),
  bottomSheetTheme: const BottomSheetThemeData(
    backgroundColor: kSurface2,
    modalBackgroundColor: kSurface2,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
  ),
);
