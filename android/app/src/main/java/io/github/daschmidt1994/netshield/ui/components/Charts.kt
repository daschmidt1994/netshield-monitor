package io.github.daschmidt1994.netshield.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.Timeseries
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic

/** Stacked bar chart of request categories over time (drawn with Canvas, no chart library). */
@Composable
fun TrafficChart(ts: Timeseries, modifier: Modifier = Modifier) {
    val c = LocalTraffic.current
    val grid = MaterialTheme.colorScheme.outlineVariant
    val series = listOf(
        stringResource(R.string.cat_visitor) to c.visitor,
        stringResource(R.string.cat_suspicious) to c.suspicious,
        stringResource(R.string.cat_challenged) to c.challenged,
        stringResource(R.string.cat_blocked) to c.blocked,
        stringResource(R.string.cat_internal) to c.internal,
    )
    val pts = ts.points
    val max = (pts.maxOfOrNull { it.total } ?: 0).coerceAtLeast(1)
    Column(modifier) {
        Box(Modifier.fillMaxWidth().height(180.dp)) {
            Canvas(Modifier.fillMaxWidth().height(180.dp)) {
                for (i in 0..3) {
                    val y = size.height * i / 3f
                    drawLine(grid, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                }
                if (pts.isEmpty()) return@Canvas
                val bw = size.width / pts.size
                pts.forEachIndexed { i, p ->
                    var y = size.height
                    val values = listOf(p.visitor, p.suspicious, p.challenged, p.blocked, p.internal)
                    values.forEachIndexed { si, v ->
                        if (v <= 0) return@forEachIndexed
                        val h = size.height * v / max
                        drawRect(series[si].second, Offset(i * bw + bw * 0.1f, y - h), Size(bw * 0.8f, h))
                        y -= h
                    }
                }
            }
            Text(fmt(max), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.TopStart))
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(top = 8.dp)) {
            series.forEach { (name, color) -> Legend(name, color) }
        }
    }
}

@Composable
fun Legend(name: String, color: Color) = Row(verticalAlignment = Alignment.CenterVertically) {
    Box(Modifier.size(10.dp).background(color, RoundedCornerShape(2.dp)))
    Text(" $name", style = MaterialTheme.typography.labelSmall)
}
