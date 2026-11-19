package app.garminuebersicht.data

import org.json.JSONArray
import org.json.JSONObject

// Kleine Helfer: org.json liefert für fehlende/null-Werte sonst 0 bzw. "null".
internal fun JSONObject.d(key: String): Double? =
    if (has(key) && !isNull(key)) optDouble(key).takeUnless { it.isNaN() } else null

internal fun JSONObject.i(key: String): Int? = d(key)?.toInt()
internal fun JSONObject.s(key: String): String? = if (has(key) && !isNull(key)) optString(key) else null
internal fun JSONObject.obj(key: String): JSONObject? = if (has(key) && !isNull(key)) optJSONObject(key) else null
internal fun JSONObject.arr(key: String): JSONArray = optJSONArray(key) ?: JSONArray()
internal inline fun <T> JSONArray.map(f: (JSONObject) -> T): List<T> = (0 until length()).map { f(getJSONObject(it)) }
internal fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }

data class SyncInfo(val ok: Boolean, val at: String?, val activities: Int, val nights: Int)
data class SyncError(val at: String?, val message: String)

data class Status(
    val version: String,
    val demo: Boolean,
    val syncing: Boolean,
    val lastSync: SyncInfo?,
    val lastError: SyncError?,
    val nextSync: String?,
    val activityCount: Int,
    val nightCount: Int,
) {
    companion object {
        fun from(j: JSONObject) = Status(
            version = j.optString("version"),
            demo = j.optBoolean("demo"),
            syncing = j.optBoolean("syncing"),
            lastSync = j.obj("lastSync")?.let { SyncInfo(it.optBoolean("ok"), it.s("at"), it.optInt("activities"), it.optInt("nights")) },
            lastError = j.obj("lastError")?.let { SyncError(it.s("at"), it.optString("message")) },
            nextSync = j.s("nextSync"),
            activityCount = j.obj("data")?.optInt("activities") ?: 0,
            nightCount = j.obj("data")?.optInt("nights") ?: 0,
        )
    }
}

data class Activity(
    val id: String,
    val name: String,
    val date: String,
    val time: String?,
    val type: String,
    val typeLabel: String,
    val durationS: Double?,
    val distanceM: Double?,
    val avgHr: Double?,
    val maxHr: Double?,
    val calories: Double?,
    val elevationM: Double?,
    val avgSpeedMs: Double?,
    val trainingEffect: Double?,
) {
    companion object {
        fun from(j: JSONObject) = Activity(
            id = j.optString("id"),
            name = j.s("name") ?: j.optString("typeLabel"),
            date = j.optString("date"),
            time = j.s("time"),
            type = j.optString("type"),
            typeLabel = j.optString("typeLabel"),
            durationS = j.d("durationS"),
            distanceM = j.d("distanceM"),
            avgHr = j.d("avgHr"),
            maxHr = j.d("maxHr"),
            calories = j.d("calories"),
            elevationM = j.d("elevationM"),
            avgSpeedMs = j.d("avgSpeedMs"),
            trainingEffect = j.d("trainingEffect"),
        )
    }
}

data class Night(
    val date: String,
    val totalS: Double?,
    val deepS: Double?,
    val lightS: Double?,
    val remS: Double?,
    val awakeS: Double?,
    val score: Double?,
    val start: String?,
    val end: String?,
    val restingHr: Double?,
    val hrv: Double?,
    val hrvWeekly: Double?,
) {
    companion object {
        fun from(j: JSONObject) = Night(
            date = j.optString("date"),
            totalS = j.d("totalS"),
            deepS = j.d("deepS"),
            lightS = j.d("lightS"),
            remS = j.d("remS"),
            awakeS = j.d("awakeS"),
            score = j.d("score"),
            start = j.s("start"),
            end = j.s("end"),
            restingHr = j.d("restingHr"),
            hrv = j.d("hrv"),
            hrvWeekly = j.d("hrvWeekly"),
        )
    }
}

data class WeekBucket(val weekStart: String, val hours: Double, val count: Int, val km: Double)
data class SportBucket(val label: String, val hours: Double, val count: Int, val km: Double)

data class Overview(
    val start: String,
    val end: String,
    val count: Int,
    val durationS: Double,
    val distanceM: Double,
    val avgHr: Double?,
    val perWeekCount: Double,
    val perWeekDurationS: Double,
    val perWeekDistanceM: Double,
    val weekly: List<WeekBucket>,
    val sports: List<SportBucket>,
    val nights: Int,
    val avgSleepS: Double?,
    val avgScore: Double?,
    val avgHrv: Double?,
    val avgRestingHr: Double?,
) {
    companion object {
        fun from(j: JSONObject): Overview {
            val t = j.getJSONObject("training")
            val s = j.getJSONObject("sleep")
            val pw = t.getJSONObject("perWeek")
            return Overview(
                start = j.optString("start"),
                end = j.optString("end"),
                count = t.optInt("count"),
                durationS = t.optDouble("durationS", 0.0),
                distanceM = t.optDouble("distanceM", 0.0),
                avgHr = t.d("avgHr"),
                perWeekCount = pw.optDouble("count", 0.0),
                perWeekDurationS = pw.optDouble("durationS", 0.0),
                perWeekDistanceM = pw.optDouble("distanceM", 0.0),
                weekly = t.arr("weekly").map { WeekBucket(it.optString("weekStart"), it.optDouble("hours"), it.optInt("count"), it.optDouble("km")) },
                sports = t.arr("sports").map { SportBucket(it.optString("label"), it.optDouble("hours"), it.optInt("count"), it.optDouble("km")) },
                nights = s.optInt("nights"),
                avgSleepS = s.d("avgTotalS"),
                avgScore = s.d("avgScore"),
                avgHrv = s.d("avgHrv"),
                avgRestingHr = s.d("avgRestingHr"),
            )
        }
    }
}

data class Zone(val zone: String, val label: String, val from: Int, val to: Int)

data class Coach(
    val date: String,
    val readiness: Int,
    val readinessLabel: String,
    val partSleep: Int,
    val partHrv: Int,
    val partLoad: Int,
    val kind: String,
    val title: String,
    val sportLabel: String,
    val durationMin: List<Int>,
    val details: List<String>,
    val reasons: List<String>,
    val weekDoneMin: Int,
    val weekTargetMin: Int,
    val acwr: Double?,
    val hrvLastNight: Double?,
    val hrvBaseline: Double?,
    val sleepScore: Double?,
    val sleepS: Double?,
    val restingHr: Int?,
    val maxHr: Int?,
    val maxHrSource: String?,
    val zones: List<Zone>,
    val hints: List<String>,
    val disclaimer: String,
) {
    companion object {
        fun from(j: JSONObject): Coach {
            val r = j.getJSONObject("readiness")
            val p = r.getJSONObject("parts")
            val t = j.getJSONObject("today")
            val w = j.getJSONObject("week")
            val m = j.getJSONObject("metrics")
            val dur = t.arr("durationMin")
            return Coach(
                date = j.optString("date"),
                readiness = r.optInt("score"),
                readinessLabel = r.optString("label"),
                partSleep = p.optInt("sleep"),
                partHrv = p.optInt("hrv"),
                partLoad = p.optInt("load"),
                kind = t.optString("kind"),
                title = t.optString("title"),
                sportLabel = t.optString("sportLabel"),
                durationMin = (0 until dur.length()).map { dur.optInt(it) },
                details = t.arr("details").strings(),
                reasons = t.arr("reasons").strings(),
                weekDoneMin = w.optInt("doneMin"),
                weekTargetMin = w.optInt("targetMin"),
                acwr = m.d("acwr"),
                hrvLastNight = m.d("hrvLastNight"),
                hrvBaseline = m.d("hrvBaseline"),
                sleepScore = m.d("sleepScore"),
                sleepS = m.d("sleepS"),
                restingHr = m.i("restingHr"),
                maxHr = m.i("maxHr"),
                maxHrSource = m.s("maxHrSource"),
                zones = j.arr("zones").map { Zone(it.optString("zone"), it.optString("label"), it.optInt("from"), it.optInt("to")) },
                hints = j.arr("hints").strings(),
                disclaimer = j.optString("disclaimer"),
            )
        }
    }
}
