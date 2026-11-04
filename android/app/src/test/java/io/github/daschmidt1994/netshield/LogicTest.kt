package io.github.daschmidt1994.netshield

import io.github.daschmidt1994.netshield.data.AppUpdate
import io.github.daschmidt1994.netshield.data.Overview
import io.github.daschmidt1994.netshield.data.RangeKey
import io.github.daschmidt1994.netshield.data.TimeRange
import io.github.daschmidt1994.netshield.data.json
import io.github.daschmidt1994.netshield.ui.components.CountryShape
import io.github.daschmidt1994.netshield.ui.components.MapViewport
import io.github.daschmidt1994.netshield.ui.components.WorldData
import io.github.daschmidt1994.netshield.ui.components.fmtDuration
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LogicTest {
    @Test fun rangeParams() {
        assertEquals(mapOf("range" to "24h"), TimeRange(RangeKey.H24).params())
        assertEquals(mapOf("from" to "100", "to" to "200"), TimeRange(RangeKey.CUSTOM, 100, 200).params())
    }

    @Test fun pointInPolygon() {
        val square = CountryShape("XX", listOf(floatArrayOf(0f, 0f, 10f, 0f, 10f, 10f, 0f, 10f, 0f, 0f)))
        assertTrue(WorldData.contains(square, 5f, 5f))
        assertFalse(WorldData.contains(square, 15f, 5f))
    }

    @Test fun mapZoomKeepsGestureCentreInPlace() {
        val v = MapViewport().transform(centroidX = 50f, centroidY = 25f, zoom = 2f, panX = 0f, panY = 0f,
            width = 100f, height = 50f)
        assertEquals(2f, v.scale, 0.001f)
        assertEquals(-50f, v.offsetX, 0.001f)
        assertEquals(-25f, v.offsetY, 0.001f)
        val (x, y) = v.toContent(50f, 25f)
        assertEquals(50f, x, 0.001f)
        assertEquals(25f, y, 0.001f)
    }

    @Test fun mapZoomIsClampedToVisibleWorld() {
        val out = MapViewport().transform(10f, 10f, 0.5f, 30f, 30f, 100f, 50f)
        assertEquals(MapViewport(), out)
        val panned = MapViewport(scale = 2f).transform(0f, 0f, 1f, -500f, -500f, 100f, 50f)
        assertEquals(-100f, panned.offsetX, 0.001f)
        assertEquals(-50f, panned.offsetY, 0.001f)
        assertEquals(MapViewport.MAX_SCALE, MapViewport().transform(0f, 0f, 100f, 0f, 0f, 100f, 50f).scale, 0.001f)
    }

    @Test fun mapDoubleTapZoomsInAndResets() {
        val zoomed = MapViewport().toggleZoom(50f, 25f, 100f, 50f)
        assertEquals(MapViewport.DOUBLE_TAP_SCALE, zoomed.scale, 0.001f)
        assertEquals(MapViewport(), zoomed.toggleZoom(10f, 10f, 100f, 50f))
    }

    @Test fun updateVersionComparison() {
        assertTrue(AppUpdate.isNewer("v0.1.3", "0.1.2"))
        assertTrue(AppUpdate.isNewer("v0.2.0", "v0.1.10"))
        assertTrue(AppUpdate.isNewer("1.0.0", "0.9.9-debug"))
        assertFalse(AppUpdate.isNewer("v0.1.2", "v0.1.2"))
        assertFalse(AppUpdate.isNewer("v0.1.1", "0.1.2"))
        assertFalse(AppUpdate.isNewer("garbage", "0.1.2"))
    }

    @Test fun updateParsesLatestReleaseApk() {
        val r = AppUpdate.parseRelease("""
            {"tag_name":"v0.1.3","html_url":"https://github.com/x/y/releases/tag/v0.1.3","draft":false,"prerelease":false,
             "assets":[{"name":"netshield_monitor.zip","browser_download_url":"https://e/zip"},
                       {"name":"netshield-monitor-v0.1.3.apk","browser_download_url":"https://e/app.apk"}]}
        """.trimIndent())
        assertEquals("v0.1.3", r?.version)
        assertEquals("https://e/app.apk", r?.apkUrl)
        assertEquals(null, AppUpdate.parseRelease("""{"tag_name":"v1","assets":[]}"""))
    }

    @Test fun durations() {
        assertEquals("3h 59m", fmtDuration(3 * 3600 + 59 * 60L))
        assertEquals("2d 1h", fmtDuration(2 * 86400 + 3600L))
        assertEquals("–", fmtDuration(null))
    }

    @Test fun parsesBackendOverviewIgnoringUnknownFields() {
        val o = json.decodeFromString(Overview.serializer(), """
            {"requests":{"requests":27,"blocked":5,"challenged":0,"suspicious":1,"internal":1,"external_requests":26,
             "would_block_observe":0,"bytes_down":1,"by_category":{}},"requests_today":27,"requests_24h":27,"blocked_24h":5,
             "visitors":{"value":5,"method":"distinct_daily_pseudonyms"},"visitors_today":{"value":5,"method":"x"},
             "active_domains":1,"known_domains":1,"requests_per_minute":1.2,"new_field":true,
             "crowdsec":{"alerts":0,"alerts_24h":3,"critical_alerts_24h":1,"local_active_decisions":2,"community_active_decisions":9},
             "top_countries":[{"country":"AT","requests":20,"blocked":0,"allowed":20},{"country":null,"requests":1,"blocked":0,"allowed":1}],
             "security_status":{"level":"warning","reasons":[{"code":"source_errors","value":["x"]}]}}
        """.trimIndent())
        assertEquals(27, o.requestsToday)
        assertEquals(5, o.requests.blocked)
        assertEquals("warning", o.securityStatus.level)
        assertEquals(null, o.topCountries[1].country)
    }
}
