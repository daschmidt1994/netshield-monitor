package io.github.daschmidt1994.netshield.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName

// Subset of the NetShield REST API (see /api/docs on the backend). Unknown fields are ignored.

@Serializable
data class Health(val status: String = "", val version: String = "", val time: Long = 0)

@Serializable
data class CategoryTotals(
    val requests: Long = 0,
    @SerialName("external_requests") val externalRequests: Long = 0,
    val blocked: Long = 0,
    val challenged: Long = 0,
    val suspicious: Long = 0,
    val internal: Long = 0,
    @SerialName("would_block_observe") val wouldBlockObserve: Long = 0,
)

@Serializable
data class Visitors(val value: Long = 0, val method: String = "")

@Serializable
data class CountryRow(val country: String? = null, val requests: Long = 0, val blocked: Long = 0, val allowed: Long = 0)

@Serializable
data class Reason(val code: String = "")

@Serializable
data class SecurityStatus(val level: String = "ok", val reasons: List<Reason> = emptyList())

@Serializable
data class CrowdsecOverview(
    val alerts: Long = 0,
    @SerialName("alerts_24h") val alerts24h: Long = 0,
    @SerialName("critical_alerts_24h") val criticalAlerts24h: Long = 0,
    @SerialName("local_active_decisions") val localActiveDecisions: Long = 0,
    @SerialName("community_active_decisions") val communityActiveDecisions: Long = 0,
)

@Serializable
data class Overview(
    val requests: CategoryTotals = CategoryTotals(),
    @SerialName("requests_today") val requestsToday: Long = 0,
    @SerialName("requests_24h") val requests24h: Long = 0,
    @SerialName("blocked_24h") val blocked24h: Long = 0,
    val visitors: Visitors = Visitors(),
    @SerialName("visitors_today") val visitorsToday: Visitors = Visitors(),
    @SerialName("active_domains") val activeDomains: Int = 0,
    @SerialName("known_domains") val knownDomains: Int = 0,
    @SerialName("requests_per_minute") val requestsPerMinute: Double = 0.0,
    val crowdsec: CrowdsecOverview = CrowdsecOverview(),
    @SerialName("top_countries") val topCountries: List<CountryRow> = emptyList(),
    @SerialName("security_status") val securityStatus: SecurityStatus = SecurityStatus(),
)

@Serializable
data class TsPoint(
    val ts: Long, val total: Long = 0, val visitor: Long = 0, val suspicious: Long = 0,
    val blocked: Long = 0, val challenged: Long = 0, val internal: Long = 0,
)

@Serializable
data class Timeseries(@SerialName("bucket_seconds") val bucketSeconds: Long = 60, val points: List<TsPoint> = emptyList())

@Serializable
data class DomainRow(
    val host: String,
    @SerialName("crowdsec_mode") val crowdsecMode: String? = null,
    val enabled: Boolean = true,
    val requests: Long = 0,
    val blocked: Long = 0,
    val suspicious: Long = 0,
    @SerialName("requests_per_minute") val requestsPerMinute: Double = 0.0,
    @SerialName("last_seen") val lastSeen: Long? = null,
)

@Serializable
data class Items<T>(val items: List<T> = emptyList())

@Serializable
data class PathRow(val host: String = "", val path: String = "", val requests: Long = 0, val blocked: Long = 0, val errors: Long = 0)

@Serializable
data class PathList(val items: List<PathRow> = emptyList())

@Serializable
data class StatusRow(val status: Int, val count: Long)

@Serializable
data class Scenario(val scenario: String, val count: Long)

@Serializable
data class AlertSummary(
    val alerts: Long = 0,
    @SerialName("alerts_with_decision") val alertsWithDecision: Long = 0,
    @SerialName("by_severity") val bySeverity: Map<String, Long> = emptyMap(),
    @SerialName("top_scenarios") val topScenarios: List<Scenario> = emptyList(),
)

@Serializable
data class DomainInfo(@SerialName("crowdsec_mode") val crowdsecMode: String? = null, val source: String = "")

@Serializable
data class DomainDetail(
    val host: String,
    val info: DomainInfo? = null,
    val requests: CategoryTotals = CategoryTotals(),
    @SerialName("requests_per_minute") val requestsPerMinute: Double = 0.0,
    val visitors: Visitors = Visitors(),
    val countries: List<CountryRow> = emptyList(),
    val statuses: List<StatusRow> = emptyList(),
    @SerialName("top_paths") val topPaths: PathList = PathList(),
    @SerialName("suspicious_paths") val suspiciousPaths: PathList = PathList(),
    val timeseries: Timeseries = Timeseries(),
    val crowdsec: AlertSummary = AlertSummary(),
)

@Serializable
data class AlertRow(
    val id: Long,
    val scenario: String,
    val created: Long,
    val events: Long = 0,
    val source: String? = null,
    val country: String? = null,
    @SerialName("as_name") val asName: String? = null,
    @SerialName("target_host") val targetHost: String? = null,
    val decisions: Int = 0,
    @SerialName("decision_type") val decisionType: String? = null,
    @SerialName("decision_duration") val decisionDuration: String? = null,
    val severity: String = "low",
)

@Serializable
data class LocalDecision(
    val id: Long, val origin: String, val type: String, val value: String, val scenario: String? = null,
    @SerialName("remaining_seconds") val remainingSeconds: Long? = null,
)

@Serializable
data class Decisions(
    @SerialName("local_active") val localActive: Long = 0,
    @SerialName("community_active") val communityActive: Long = 0,
    @SerialName("local_decisions") val localDecisions: List<LocalDecision> = emptyList(),
)

@Serializable
data class Enforcement(val blocked: Long? = null, val challenged: Long? = null,
                       @SerialName("would_block_observe") val wouldBlockObserve: Long? = null, val evidence: String = "")

@Serializable
data class CrowdsecSummary(
    val alerts: AlertSummary = AlertSummary(),
    val decisions: Decisions = Decisions(),
    val enforcement: Map<String, Enforcement> = emptyMap(),
)

@Serializable
data class NotificationRow(
    val id: Long, val ts: Long, val kind: String, val severity: String, val title: String, val message: String,
    val host: String? = null,
)

@Serializable
data class SourceRow(val name: String, val configured: Boolean = false, val status: String? = null,
                     @SerialName("last_error") val lastError: String? = null)

@Serializable
data class Sources(val sources: List<SourceRow> = emptyList(), val version: String = "")
