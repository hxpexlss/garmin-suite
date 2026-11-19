package app.garminuebersicht.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException

class ApiException(message: String) : IOException(message)

/** Verbindungsdaten, lokal in den SharedPreferences gespeichert. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString("serverUrl", "") ?: ""
        set(v) = prefs.edit().putString("serverUrl", v.trim().trimEnd('/')).apply()

    var token: String
        get() = prefs.getString("token", "") ?: ""
        set(v) = prefs.edit().putString("token", v.trim()).apply()

    val configured: Boolean get() = serverUrl.isNotBlank()
}

class Api(private val baseUrl: String, private val token: String) {

    suspend fun status() = Status.from(get("/api/status"))
    suspend fun overview(days: Int) = Overview.from(get("/api/overview?days=$days"))
    suspend fun activities(days: Int) = get("/api/activities?days=$days").arr("activities").map { Activity.from(it) }
    suspend fun sleep(days: Int) = get("/api/sleep?days=$days").arr("nights").map { Night.from(it) }
    suspend fun coach() = Coach.from(get("/api/coach"))
    suspend fun triggerSync(): Boolean = request("POST", "/api/sync").optBoolean("started")

    private suspend fun get(path: String) = request("GET", path)

    private suspend fun request(method: String, path: String): JSONObject = withContext(Dispatchers.IO) {
        if (baseUrl.isBlank()) throw ApiException("Keine Server-Adresse eingestellt")
        val conn = try {
            URL(baseUrl + path).openConnection() as HttpURLConnection
        } catch (e: Exception) {
            throw ApiException("Ungültige Server-Adresse: $baseUrl")
        }
        try {
            conn.requestMethod = method
            conn.connectTimeout = 8_000
            conn.readTimeout = 20_000
            conn.setRequestProperty("Accept", "application/json")
            if (token.isNotBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
            if (method == "POST") {
                conn.doOutput = true
                conn.setFixedLengthStreamingMode(0)
                conn.outputStream.close()
            }
            val code = conn.responseCode
            val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            when {
                code == 401 -> throw ApiException("Token fehlt oder ist falsch (401)")
                code == 409 -> JSONObject(body.ifBlank { "{}" })
                code !in 200..299 -> {
                    val msg = runCatching { JSONObject(body).optString("error") }.getOrNull()
                    throw ApiException("Server meldet $code${if (!msg.isNullOrBlank()) ": $msg" else ""}")
                }
                else -> JSONObject(body)
            }
        } catch (e: ApiException) {
            throw e
        } catch (e: UnknownHostException) {
            throw ApiException("Server nicht gefunden – ist Tailscale auf dem Handy verbunden?")
        } catch (e: SocketTimeoutException) {
            throw ApiException("Zeitüberschreitung – ist Tailscale verbunden und der Server erreichbar?")
        } catch (e: java.net.ConnectException) {
            throw ApiException("Verbindung abgelehnt – läuft der Server und stimmt der Port?")
        } catch (e: javax.net.ssl.SSLException) {
            throw ApiException("TLS-Fehler: ${e.message}")
        } catch (e: org.json.JSONException) {
            throw ApiException("Unerwartete Antwort vom Server")
        } catch (e: IOException) {
            throw ApiException("Netzwerkfehler: ${e.message}")
        } finally {
            conn.disconnect()
        }
    }
}
