package io.github.daschmidt1994.netshield.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

@Immutable
data class TrafficColors(
    val visitor: Color, val suspicious: Color, val blocked: Color, val challenged: Color, val internal: Color,
    val ok: Color, val warn: Color, val bad: Color,
)

private val LightTraffic = TrafficColors(
    visitor = Color(0xFF2563EB), suspicious = Color(0xFFD97706), blocked = Color(0xFFDC2626),
    challenged = Color(0xFF9333EA), internal = Color(0xFF64748B),
    ok = Color(0xFF15803D), warn = Color(0xFFB45309), bad = Color(0xFFC2410C),
)
private val DarkTraffic = TrafficColors(
    visitor = Color(0xFF60A5FA), suspicious = Color(0xFFFBBF24), blocked = Color(0xFFF87171),
    challenged = Color(0xFFC084FC), internal = Color(0xFF94A3B8),
    ok = Color(0xFF4ADE80), warn = Color(0xFFFBBF24), bad = Color(0xFFFB7185),
)
val LocalTraffic = staticCompositionLocalOf { LightTraffic }

@Composable
fun NetShieldTheme(themeSetting: String = "system", content: @Composable () -> Unit) {
    val dark = when (themeSetting) { "dark" -> true; "light" -> false; else -> isSystemInDarkTheme() }
    val ctx = LocalContext.current
    val scheme = when {
        Build.VERSION.SDK_INT >= 31 -> if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        dark -> darkColorScheme(primary = Color(0xFF60A5FA))
        else -> lightColorScheme(primary = Color(0xFF2563EB))
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalTraffic provides if (dark) DarkTraffic else LightTraffic) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}
