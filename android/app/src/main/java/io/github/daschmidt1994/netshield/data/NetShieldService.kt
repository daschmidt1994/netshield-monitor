package io.github.daschmidt1994.netshield.data

import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.QueryMap
import retrofit2.http.Query

interface NetShieldService {
    @GET("api/v1/health") suspend fun health(): Health
    @GET("api/v1/sources") suspend fun sources(): Sources
    @GET("api/v1/overview") suspend fun overview(@QueryMap range: Map<String, String>): Overview
    @GET("api/v1/timeseries") suspend fun timeseries(@QueryMap range: Map<String, String>): Timeseries
    @GET("api/v1/countries") suspend fun countries(@QueryMap range: Map<String, String>, @Query("host") host: String? = null): Items<CountryRow>
    @GET("api/v1/domains") suspend fun domains(@QueryMap range: Map<String, String>): Items<DomainRow>
    @GET("api/v1/domains/{host}") suspend fun domain(@Path("host") host: String, @QueryMap range: Map<String, String>): DomainDetail
    @GET("api/v1/crowdsec/summary") suspend fun crowdsec(@QueryMap range: Map<String, String>): CrowdsecSummary
    @GET("api/v1/crowdsec/alerts") suspend fun alerts(@QueryMap range: Map<String, String>, @Query("limit") limit: Int = 50): Items<AlertRow>
    @GET("api/v1/crowdsec/decisions") suspend fun decisions(): Decisions
    @GET("api/v1/notifications") suspend fun notifications(@Query("after_id") afterId: Long? = null, @Query("limit") limit: Int = 50): Items<NotificationRow>
}
