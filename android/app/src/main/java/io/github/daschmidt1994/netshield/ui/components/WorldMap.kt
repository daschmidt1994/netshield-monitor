package io.github.daschmidt1994.netshield.ui.components

import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.double
import kotlin.math.sqrt

/** One country: ISO alpha-2 code and its rings in lon/lat (Natural Earth 110m, public domain). */
class CountryShape(val code: String, val rings: List<FloatArray>)

private const val LAT_TOP = 84f
private const val LAT_BOTTOM = -58f

object WorldData {
    @Volatile private var cache: List<CountryShape>? = null

    suspend fun load(ctx: Context): List<CountryShape> = cache ?: withContext(Dispatchers.Default) {
        val text = ctx.assets.open("world.json").bufferedReader().use { it.readText() }
        val root = Json.parseToJsonElement(text).jsonObject
        val out = root["features"]!!.jsonArray.map { f ->
            val o = f.jsonObject
            val geom = o["geometry"]!!.jsonObject
            val type = geom["type"]!!.jsonPrimitive.content
            val coords = geom["coordinates"]!!.jsonArray
            val polygons = if (type == "Polygon") listOf(coords) else coords.map { it.jsonArray }
            val rings = polygons.flatMap { poly -> poly.map { ring -> toArray(ring.jsonArray) } }
            CountryShape(o["id"]!!.jsonPrimitive.content, rings)
        }
        cache = out
        out
    }

    private fun toArray(ring: JsonArray): FloatArray {
        val a = FloatArray(ring.size * 2)
        ring.forEachIndexed { i, p ->
            val pt = p.jsonArray
            a[i * 2] = pt[0].jsonPrimitive.double.toFloat()
            a[i * 2 + 1] = pt[1].jsonPrimitive.double.toFloat()
        }
        return a
    }

    fun contains(shape: CountryShape, lon: Float, lat: Float): Boolean {
        var inside = false
        for (ring in shape.rings) {
            var j = ring.size / 2 - 1
            for (i in 0 until ring.size / 2) {
                val xi = ring[i * 2]; val yi = ring[i * 2 + 1]; val xj = ring[j * 2]; val yj = ring[j * 2 + 1]
                if ((yi > lat) != (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside
                j = i
            }
        }
        return inside
    }
}

/**
 * Choropleth world map. [values] maps ISO alpha-2 codes to counts. Colour intensity uses a square-root
 * scale so a few large countries do not wash out the rest. Locations are approximate (GeoIP).
 */
@Composable
fun WorldMap(values: Map<String, Long>, high: Color, modifier: Modifier = Modifier, onTap: (String) -> Unit = {}) {
    val ctx = LocalContext.current
    var shapes by remember { mutableStateOf<List<CountryShape>>(emptyList()) }
    LaunchedEffect(Unit) { shapes = WorldData.load(ctx) }
    val base = MaterialTheme.colorScheme.surfaceVariant
    val border = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f)
    val max = (values.values.maxOrNull() ?: 0).coerceAtLeast(1)
    Canvas(
        modifier.fillMaxWidth().aspectRatio(2.1f).pointerInput(shapes) {
            detectTapGestures { pos ->
                val lon = pos.x / size.width * 360f - 180f
                val lat = LAT_TOP - pos.y / size.height * (LAT_TOP - LAT_BOTTOM)
                shapes.firstOrNull { WorldData.contains(it, lon, lat) }?.let { onTap(it.code) }
            }
        }
    ) {
        val sx = size.width / 360f
        val sy = size.height / (LAT_TOP - LAT_BOTTOM)
        for (shape in shapes) {
            val path = Path()
            for (ring in shape.rings) {
                for (i in 0 until ring.size / 2) {
                    val x = (ring[i * 2] + 180f) * sx
                    val y = (LAT_TOP - ring[i * 2 + 1]) * sy
                    if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                path.close()
            }
            val v = values[shape.code] ?: 0
            val color = if (v > 0) lerp(base, high, (0.2f + 0.8f * sqrt(v.toFloat() / max)).coerceIn(0f, 1f)) else base
            drawPath(path, color)
            drawPath(path, border, style = Stroke(width = 0.6f))
        }
    }
}
