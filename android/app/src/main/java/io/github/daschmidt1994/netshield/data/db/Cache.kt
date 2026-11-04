package io.github.daschmidt1994.netshield.data.db

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase

/** Last successful API responses, so the app shows data (marked as cached) while offline. */
@Entity(tableName = "cached_responses")
data class CachedResponse(@PrimaryKey val key: String, val json: String, val fetchedAt: Long)

@Entity(tableName = "notifications")
data class StoredNotification(
    @PrimaryKey val id: Long, val ts: Long, val kind: String, val severity: String, val title: String,
    val message: String, val host: String?,
)

@Dao
interface CacheDao {
    @Query("SELECT * FROM cached_responses WHERE `key` = :key")
    suspend fun get(key: String): CachedResponse?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun put(item: CachedResponse)

    @Query("DELETE FROM cached_responses")
    suspend fun clear()

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun putNotifications(items: List<StoredNotification>)

    @Query("SELECT * FROM notifications ORDER BY id DESC LIMIT :limit")
    suspend fun notifications(limit: Int = 50): List<StoredNotification>

    @Query("DELETE FROM notifications WHERE ts < :before")
    suspend fun pruneNotifications(before: Long)
}

@Database(entities = [CachedResponse::class, StoredNotification::class], version = 1, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun cache(): CacheDao

    companion object {
        @Volatile private var instance: AppDatabase? = null
        fun get(context: Context): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(context.applicationContext, AppDatabase::class.java, "netshield.db")
                .fallbackToDestructiveMigration(dropAllTables = true)
                .build().also { instance = it }
        }
    }
}
