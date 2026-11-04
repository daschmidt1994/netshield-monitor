package io.github.daschmidt1994.netshield.ui.components

import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
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
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
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
 * Zoom/pan state of the world map in canvas pixels. Content point p is drawn at p * scale + offset.
 * Pure logic (no Compose) so it can be unit-tested.
 */
data class MapViewport(val scale: Float = 1f, val offsetX: Float = 0f, val offsetY: Float = 0f) {
    /** Apply a gesture step: zoom around the gesture centroid, then pan; clamped to the visible world. */
    fun transform(centroidX: Float, centroidY: Float, zoom: Float, panX: Float, panY: Float,
                  width: Float, height: Float): MapViewport {
        val ns = (scale * zoom).coerceIn(MIN_SCALE, MAX_SCALE)
        val f = ns / scale
        val ox = centroidX - (centroidX - offsetX) * f + panX
        val oy = centroidY - (centroidY - offsetY) * f + panY
        return clamped(ns, ox, oy, width, height)
    }

    /** Double tap: zoom in around the tapped point, or reset when already zoomed. */
    fun toggleZoom(x: Float, y: Float, width: Float, height: Float): MapViewport =
        if (scale > MIN_SCALE) MapViewport()
        else MapViewport().transform(x, y, DOUBLE_TAP_SCALE, 0f, 0f, width, height)

    /** Screen position → unzoomed canvas position (for hit testing). */
    fun toContent(x: Float, y: Float): Pair<Float, Float> = ((x - offsetX) / scale) to ((y - offsetY) / scale)

    companion object {
        const val MIN_SCALE = 1f
        const val MAX_SCALE = 8f
        const val DOUBLE_TAP_SCALE = 2.5f

        private fun clamped(s: Float, ox: Float, oy: Float, w: Float, h: Float): MapViewport {
            if (s <= MIN_SCALE) return MapViewport()
            return MapViewport(s, ox.coerceIn(w * (1f - s), 0f), oy.coerceIn(h * (1f - s), 0f))
        }
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
    var viewport by remember { mutableStateOf(MapViewport()) }
    Canvas(
        modifier.fillMaxWidth().aspectRatio(2.1f).clipToBounds()
            // Pinch to zoom; one-finger drag pans only while zoomed, so the screen still scrolls normally.
            .pointerInput(Unit) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    do {
                        val event = awaitPointerEvent()
                        val fingers = event.changes.count { it.pressed }
                        if (fingers >= 2 || viewport.scale > MapViewport.MIN_SCALE) {
                            val c = event.calculateCentroid(useCurrent = false)
                            val pan = event.calculatePan()
                            if (c != Offset.Unspecified) {
                                viewport = viewport.transform(c.x, c.y, event.calculateZoom(), pan.x, pan.y,
                                    size.width.toFloat(), size.height.toFloat())
                            }
                            event.changes.forEach { if (it.positionChanged()) it.consume() }
                        }
                    } while (event.changes.any { it.pressed })
                }
            }
            .pointerInput(shapes) {
                detectTapGestures(
                    onDoubleTap = { pos ->
                        viewport = viewport.toggleZoom(pos.x, pos.y, size.width.toFloat(), size.height.toFloat())
                    },
                ) { pos ->
                    val (x, y) = viewport.toContent(pos.x, pos.y)
                    val lon = x / size.width * 360f - 180f
                    val lat = LAT_TOP - y / size.height * (LAT_TOP - LAT_BOTTOM)
                    shapes.firstOrNull { WorldData.contains(it, lon, lat) }?.let { onTap(it.code) }
                }
            }
    ) {
        val sx = size.width / 360f * viewport.scale
        val sy = size.height / (LAT_TOP - LAT_BOTTOM) * viewport.scale
        val ox = viewport.offsetX
        val oy = viewport.offsetY
        for (shape in shapes) {
            val path = Path()
            for (ring in shape.rings) {
                for (i in 0 until ring.size / 2) {
                    val x = (ring[i * 2] + 180f) * sx + ox
                    val y = (LAT_TOP - ring[i * 2 + 1]) * sy + oy
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
