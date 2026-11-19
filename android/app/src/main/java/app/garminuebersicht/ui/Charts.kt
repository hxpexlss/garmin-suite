package app.garminuebersicht.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.pow

data class Series(val name: String, val color: Color, val values: List<Float?>)

/** Gut lesbare Achsenschritte: 1, 2, 5, 10 … */
private fun niceStep(raw: Float): Float {
    if (raw <= 0f) return 1f
    val p = 10.0.pow(floor(log10(raw.toDouble()))).toFloat()
    for (m in floatArrayOf(1f, 2f, 5f, 10f)) if (m * p >= raw) return m * p
    return 10 * p
}

@Composable
fun Legend(items: List<Pair<String, Color>>, line: Boolean = false) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        items.forEach { (name, color) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(width = if (line) 14.dp else 10.dp, height = if (line) 2.dp else 10.dp)
                    .background(color, RoundedCornerShape(if (line) 1.dp else 3.dp)))
                Spacer(Modifier.width(5.dp))
                Text(name, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Info-Zeile über einem Diagramm: zeigt den angetippten Wert. */
@Composable
private fun SelectionLine(text: String?) {
    Text(
        text ?: "Antippen für Details",
        style = MaterialTheme.typography.bodySmall,
        color = if (text == null) LocalChartColors.current.muted else MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.heightIn(min = 18.dp).padding(bottom = 4.dp),
    )
}

/** Säulendiagramm, optional gestapelt (Reihenfolge der Serien = von unten nach oben). */
@Composable
fun ColumnChart(
    labels: List<String>,
    series: List<Series>,
    yFmt: (Float) -> String,
    detail: (Int) -> String,
    height: Int = 200,
) {
    val c = LocalChartColors.current
    val measurer = rememberTextMeasurer()
    val labelStyle = TextStyle(color = c.muted, fontSize = 10.sp)
    var selected by remember(labels, series) { mutableStateOf<Int?>(null) }
    Column {
        SelectionLine(selected?.let(detail))
        if (labels.isEmpty()) { Empty(); return@Column }
        Canvas(
            Modifier.fillMaxWidth().height(height.dp).pointerInput(labels.size) {
                detectTapGestures { pos ->
                    val left = 34.dp.toPx()
                    val band = (size.width - left) / labels.size
                    val i = ((pos.x - left) / band).toInt()
                    selected = if (i in labels.indices && i != selected) i else null
                }
            }
        ) {
            val left = 34.dp.toPx(); val bottom = 18.dp.toPx(); val top = 6.dp.toPx()
            val ih = size.height - bottom - top; val iw = size.width - left
            val totals = labels.indices.map { i -> series.sumOf { (it.values.getOrNull(i) ?: 0f).toDouble() }.toFloat() }
            val maxV = totals.maxOrNull() ?: 0f
            val step = niceStep(maxV / 4)
            val ticks = max(1, ceil(maxV / step).toInt())
            val yMax = step * ticks
            fun y(v: Float) = top + ih - v / yMax * ih
            for (k in 0..ticks) {
                val yy = y(step * k)
                drawLine(if (k == 0) c.axis else c.grid, Offset(left, yy), Offset(size.width, yy), 1.dp.toPx())
                val t = measurer.measure(yFmt(step * k), labelStyle)
                drawText(t, topLeft = Offset(left - 6.dp.toPx() - t.size.width, yy - t.size.height / 2))
            }
            val band = iw / labels.size
            val bw = minOf(24.dp.toPx(), band - 2.dp.toPx()).coerceAtLeast(1f)
            val gap = 2.dp.toPx(); val r = 4.dp.toPx()
            val every = max(1, ceil(labels.size / (iw / 48.dp.toPx())).toInt())
            labels.forEachIndexed { i, label ->
                val x = left + band * i + (band - bw) / 2
                if (i == selected) drawRect(c.grid.copy(alpha = 0.6f), Offset(left + band * i, top), Size(band, ih))
                var acc = 0f
                val topIdx = series.indexOfLast { (it.values.getOrNull(i) ?: 0f) > 0f }
                series.forEachIndexed { si, s ->
                    val v = s.values.getOrNull(i) ?: 0f
                    if (v <= 0f) return@forEachIndexed
                    val y0 = y(acc); val y1 = y(acc + v); acc += v
                    val h = y0 - y1 - if (acc - v > 0f) gap else 0f
                    if (h <= 0f) return@forEachIndexed
                    if (si == topIdx) roundTopRect(s.color, x, y1, bw, h, r) else drawRect(s.color, Offset(x, y1), Size(bw, h))
                }
                if (i % every == 0) {
                    val t = measurer.measure(label, labelStyle)
                    drawText(t, topLeft = Offset(x + bw / 2 - t.size.width / 2, size.height - t.size.height))
                }
            }
        }
    }
}

private fun DrawScope.roundTopRect(color: Color, x: Float, y: Float, w: Float, h: Float, r: Float) {
    val rr = minOf(r, w / 2, h)
    val path = Path().apply {
        addRoundRect(RoundRect(x, y, x + w, y + h, topLeftCornerRadius = CornerRadius(rr), topRightCornerRadius = CornerRadius(rr),
            bottomLeftCornerRadius = CornerRadius.Zero, bottomRightCornerRadius = CornerRadius.Zero))
    }
    drawPath(path, color)
}

/** Liniendiagramm über Tage; Lücken (null) unterbrechen die Linie. */
@Composable
fun LineChart(
    labels: List<String>,
    series: List<Series>,
    yFmt: (Float) -> String,
    detail: (Int) -> String,
    fixedMin: Float? = null,
    fixedMax: Float? = null,
    area: Boolean = false,
    height: Int = 170,
) {
    val c = LocalChartColors.current
    val measurer = rememberTextMeasurer()
    val labelStyle = TextStyle(color = c.muted, fontSize = 10.sp)
    var selected by remember(labels, series) { mutableStateOf<Int?>(null) }
    val all = series.flatMap { s -> s.values.filterNotNull() }
    Column {
        SelectionLine(selected?.let(detail))
        if (all.isEmpty()) { Empty(); return@Column }
        Canvas(
            Modifier.fillMaxWidth().height(height.dp).pointerInput(labels.size) {
                detectTapGestures { pos ->
                    val left = 34.dp.toPx(); val right = 8.dp.toPx()
                    val n = labels.size
                    val i = if (n <= 1) 0 else (((pos.x - left) / (size.width - left - right)) * (n - 1)).let { kotlin.math.round(it).toInt() }
                    selected = i.coerceIn(0, n - 1).takeIf { it != selected }
                }
            }
        ) {
            val left = 34.dp.toPx(); val right = 8.dp.toPx(); val bottom = 18.dp.toPx(); val top = 8.dp.toPx()
            val iw = size.width - left - right; val ih = size.height - top - bottom
            var lo = fixedMin ?: (all.min() * 0.9f)
            var hi = fixedMax ?: all.max()
            val step = niceStep((hi - lo).coerceAtLeast(1f) / 4)
            lo = floor(lo / step) * step
            hi = lo + step * max(1, ceil((hi - lo) / step).toInt())
            val n = labels.size
            fun x(i: Int) = left + if (n <= 1) iw / 2 else i.toFloat() / (n - 1) * iw
            fun y(v: Float) = top + ih - (v - lo) / (hi - lo) * ih
            var v = lo
            while (v <= hi + step / 1000) {
                drawLine(if (v == lo) c.axis else c.grid, Offset(left, y(v)), Offset(size.width - right, y(v)), 1.dp.toPx())
                val t = measurer.measure(yFmt(v), labelStyle)
                drawText(t, topLeft = Offset(left - 6.dp.toPx() - t.size.width, y(v) - t.size.height / 2))
                v += step
            }
            val every = max(1, ceil(n / (iw / 56.dp.toPx())).toInt())
            labels.forEachIndexed { i, l ->
                if (i % every == 0) {
                    val t = measurer.measure(l, labelStyle)
                    drawText(t, topLeft = Offset((x(i) - t.size.width / 2).coerceIn(0f, size.width - t.size.width), size.height - t.size.height))
                }
            }
            selected?.let { drawLine(c.axis, Offset(x(it), top), Offset(x(it), top + ih), 1.dp.toPx()) }
            series.forEach { s ->
                val line = Path(); val fill = Path()
                var pen = false; var segStart = -1; var last = -1
                fun closeFill() { if (segStart >= 0) { fill.lineTo(x(last), y(lo)); fill.lineTo(x(segStart), y(lo)); fill.close() } }
                s.values.forEachIndexed { i, value ->
                    if (value == null) { pen = false; closeFill(); segStart = -1; return@forEachIndexed }
                    if (pen) line.lineTo(x(i), y(value)) else line.moveTo(x(i), y(value))
                    if (segStart < 0) { segStart = i; fill.moveTo(x(i), y(value)) } else fill.lineTo(x(i), y(value))
                    pen = true; last = i
                }
                closeFill()
                if (area) drawPath(fill, c.wash)
                drawPath(line, s.color, style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
                val mark = selected ?: s.values.indexOfLast { it != null }
                s.values.getOrNull(mark)?.let { mv ->
                    drawCircle(s.color, 4.dp.toPx(), Offset(x(mark), y(mv)))
                }
            }
        }
    }
}

/** Horizontale Balken für Kategorien (z. B. Sportarten). */
@Composable
fun HBars(rows: List<Triple<String, Float, String>>) {
    val c = LocalChartColors.current
    if (rows.isEmpty()) { Empty(); return }
    val maxV = rows.maxOf { it.second }.coerceAtLeast(0.0001f)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        rows.forEach { (label, value, text) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.width(110.dp), maxLines = 1)
                Box(Modifier.weight(1f)) {
                    Box(Modifier.fillMaxWidth(value / maxV).height(16.dp)
                        .background(c.s1, RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp)))
                }
                Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.width(64.dp).padding(start = 6.dp))
            }
        }
    }
}

/** Fortschrittsbalken; die Spur ist eine hellere Stufe derselben Farbe. */
@Composable
fun Meter(fraction: Float, color: Color, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(8.dp).background(color.copy(alpha = 0.18f), RoundedCornerShape(4.dp))) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).height(8.dp).background(color, RoundedCornerShape(4.dp)))
    }
}

@Composable
fun Empty() {
    Text("Keine Daten im Zeitraum", style = MaterialTheme.typography.bodySmall, color = LocalChartColors.current.muted,
        modifier = Modifier.padding(vertical = 24.dp))
}
