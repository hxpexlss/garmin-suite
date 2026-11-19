package app.garminuebersicht.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/** Diagrammfarben: feste Reihenfolge, für hell und dunkel getrennt abgestimmt. */
@Immutable
data class ChartColors(
    val s1: Color, val s2: Color, val s3: Color, val s4: Color,
    val grid: Color, val axis: Color, val muted: Color, val wash: Color,
    val good: Color, val warn: Color, val bad: Color,
)

private val LightChart = ChartColors(
    s1 = Color(0xFF2A78D6), s2 = Color(0xFFEB6834), s3 = Color(0xFF1BAF7A), s4 = Color(0xFFEDA100),
    grid = Color(0xFFE1E0D9), axis = Color(0xFFC3C2B7), muted = Color(0xFF898781), wash = Color(0x1A2A78D6),
    good = Color(0xFF0CA30C), warn = Color(0xFFFAB219), bad = Color(0xFFD03B3B),
)
private val DarkChart = ChartColors(
    s1 = Color(0xFF3987E5), s2 = Color(0xFFD95926), s3 = Color(0xFF199E70), s4 = Color(0xFFC98500),
    grid = Color(0xFF2C2C2A), axis = Color(0xFF383835), muted = Color(0xFF898781), wash = Color(0x1F3987E5),
    good = Color(0xFF0CA30C), warn = Color(0xFFFAB219), bad = Color(0xFFD03B3B),
)

val LocalChartColors = staticCompositionLocalOf { LightChart }

private val LightScheme = lightColorScheme(
    primary = Color(0xFF2A78D6), onPrimary = Color.White,
    primaryContainer = Color(0xFFCDE2FB), onPrimaryContainer = Color(0xFF0D366B),
    background = Color(0xFFF9F9F7), onBackground = Color(0xFF0B0B0B),
    surface = Color(0xFFF9F9F7), onSurface = Color(0xFF0B0B0B),
    surfaceContainerLow = Color(0xFFFCFCFB), surfaceContainer = Color(0xFFF3F3F0),
    surfaceVariant = Color(0xFFF0EFEC), onSurfaceVariant = Color(0xFF52514E),
    outlineVariant = Color(0xFFE1E0D9), error = Color(0xFFD03B3B),
    errorContainer = Color(0xFFFBE4E2), onErrorContainer = Color(0xFF6B1414),
)
private val DarkScheme = darkColorScheme(
    primary = Color(0xFF6DA7EC), onPrimary = Color(0xFF0D366B),
    primaryContainer = Color(0xFF184F95), onPrimaryContainer = Color(0xFFCDE2FB),
    background = Color(0xFF0D0D0D), onBackground = Color(0xFFF0EFEC),
    surface = Color(0xFF0D0D0D), onSurface = Color(0xFFF0EFEC),
    surfaceContainerLow = Color(0xFF1A1A19), surfaceContainer = Color(0xFF222221),
    surfaceVariant = Color(0xFF2C2C2A), onSurfaceVariant = Color(0xFFC3C2B7),
    outlineVariant = Color(0xFF2C2C2A), error = Color(0xFFE66767),
    errorContainer = Color(0xFF4A1A1A), onErrorContainer = Color(0xFFFBE4E2),
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    androidx.compose.runtime.CompositionLocalProvider(LocalChartColors provides if (dark) DarkChart else LightChart) {
        MaterialTheme(colorScheme = if (dark) DarkScheme else LightScheme, content = content)
    }
}
