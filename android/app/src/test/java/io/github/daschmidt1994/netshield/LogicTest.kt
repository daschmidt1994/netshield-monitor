package io.github.daschmidt1994.netshield

import io.github.daschmidt1994.netshield.data.Overview
import io.github.daschmidt1994.netshield.data.RangeKey
import io.github.daschmidt1994.netshield.data.TimeRange
import io.github.daschmidt1994.netshield.data.json
import io.github.daschmidt1994.netshield.ui.components.CountryShape
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
