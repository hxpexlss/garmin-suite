package app.garminuebersicht.ui

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt

private val DE = Locale.GERMANY
const val DASH = "–"

fun num(v: Double?, digits: Int = 0): String =
    if (v == null) DASH else String.format(DE, "%,.${digits}f", v)

fun hm(seconds: Double?): String {
    if (seconds == null) return DASH
    val m = (seconds / 60).roundToInt()
    return "%d:%02d h".format(m / 60, m % 60)
}

fun km(meters: Double?): String = if (meters == null || meters <= 0) DASH else "${num(meters / 1000, 1)} km"

fun pace(type: String, speed: Double?, dist: Double?): String {
    if (speed == null || speed <= 0 || dist == null || dist <= 0) return DASH
    fun mmss(s: Double) = "%d:%02d".format((s / 60).toInt(), (s % 60).roundToInt().coerceAtMost(59))
    return when {
        Regex("run|walk|hik").containsMatchIn(type) -> "${mmss(1000 / speed)} /km"
        type.contains("swim") -> "${mmss(100 / speed)} /100 m"
        else -> "${num(speed * 3.6, 1)} km/h"
    }
}

fun dayLabel(iso: String, pattern: String = "EE, dd.MM."): String =
    runCatching { LocalDate.parse(iso).format(DateTimeFormatter.ofPattern(pattern, DE)) }.getOrDefault(iso)

fun dateTimeLabel(iso: String?): String {
    if (iso.isNullOrBlank()) return DASH
    return runCatching {
        val t = LocalDateTime.parse(iso)
        val day = when (t.toLocalDate()) {
            LocalDate.now() -> "heute"
            LocalDate.now().minusDays(1) -> "gestern"
            LocalDate.now().plusDays(1) -> "morgen"
            else -> t.format(DateTimeFormatter.ofPattern("dd.MM.", DE))
        }
        "$day ${t.format(DateTimeFormatter.ofPattern("HH:mm", DE))}"
    }.getOrDefault(iso)
}

fun minutesRange(r: List<Int>): String = when {
    r.isEmpty() -> ""
    r.size == 1 || r[0] == r[1] -> "${r[0]} min"
    r[0] == 0 -> "bis ${r[1]} min"
    else -> "${r[0]}–${r[1]} min"
}

fun minutesHm(min: Int): String = "%d:%02d h".format(min / 60, min % 60)
