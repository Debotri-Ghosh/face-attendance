import React, { useState, useRef, useEffect, useCallback } from "react";

const API_URL = "http://localhost:8002";

function captureFromVideo(videoRef) {
  const video = videoRef.current;
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 320;
  canvas.height = video.videoHeight || 240;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.8);
}

function Webcam({ videoRef, active }) {
  useEffect(() => {
    if (!active) return;
    let stream;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 320, height: 240 } })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch((err) => console.error("Camera error:", err));
    return () => {
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, [active, videoRef]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      style={styles.video}
    />
  );
}

function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const endpoint = isRegister ? "/auth/register" : "/auth/login";
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div style={styles.wrap}>
      <form style={styles.card} onSubmit={submit}>
        <h1 style={styles.title}>🎯 Attendance Admin</h1>
        <input style={styles.input} type="email" placeholder="Admin email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
        <input style={styles.input} type="password" placeholder="Password" value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={6} />
        {error && <div style={styles.error}>{error}</div>}
        <button style={styles.btnPrimary}>{isRegister ? "Register" : "Login"}</button>
        <p style={styles.switchText}>
          <span style={styles.switchLink} onClick={() => setIsRegister(!isRegister)}>
            {isRegister ? "Already registered? Login" : "First time? Register admin"}
          </span>
        </p>
      </form>
    </div>
  );
}

function RegisterEmployee({ token, onDone }) {
  const videoRef = useRef(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [captures, setCaptures] = useState([]);
  const [status, setStatus] = useState("");

  const capture = () => {
    const dataUrl = captureFromVideo(videoRef);
    setCaptures((c) => [...c, dataUrl]);
  };

  const submit = async () => {
    if (captures.length === 0) {
      setStatus("Capture at least 1 photo first");
      return;
    }
    setStatus("Registering...");
    const res = await fetch(`${API_URL}/employees/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, employee_code: code, face_images: captures }),
    });
    const data = await res.json();
    if (res.ok) {
      setStatus(`✅ Registered ${data.name}`);
      setCaptures([]);
      setName("");
      setCode("");
      onDone();
    } else {
      setStatus(`❌ ${data.detail}`);
    }
  };

  return (
    <div style={styles.panel}>
      <h2 style={styles.panelTitle}>Register New Employee</h2>
      <Webcam videoRef={videoRef} active={true} />
      <input style={styles.input} placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} />
      <input style={styles.input} placeholder="Employee code" value={code} onChange={(e) => setCode(e.target.value)} />
      <button style={styles.btnSecondary} onClick={capture}>📸 Capture Photo ({captures.length} taken)</button>
      <button style={styles.btnPrimary} onClick={submit}>Register Employee</button>
      {status && <div style={styles.status}>{status}</div>}
    </div>
  );
}

function MarkAttendance() {
  const videoRef = useRef(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const mark = async () => {
    setLoading(true);
    setResult(null);
    const dataUrl = captureFromVideo(videoRef);
    try {
      const res = await fetch(`${API_URL}/attendance/mark`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ matched: false, message: "Error: " + err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.panel}>
      <h2 style={styles.panelTitle}>Mark Attendance</h2>
      <Webcam videoRef={videoRef} active={true} />
      <button style={styles.btnPrimary} onClick={mark} disabled={loading}>
        {loading ? "Scanning..." : "📷 Capture & Mark Attendance"}
      </button>
      {result && (
        <div
          style={{
            ...styles.resultBox,
            borderColor: result.matched ? "#22c55e" : "#ef4444",
          }}
        >
          {result.matched ? (
            <>
              <div style={styles.resultName}>✅ {result.name}</div>
              <div style={styles.resultSub}>{result.message}</div>
            </>
          ) : (
            <div style={styles.resultSub}>❌ {result.message}</div>
          )}
        </div>
      )}
    </div>
  );
}

function Dashboard({ token }) {
  const [report, setReport] = useState(null);

  const fetchReport = useCallback(async () => {
    const res = await fetch(`${API_URL}/attendance/report`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setReport(await res.json());
  }, [token]);

  useEffect(() => {
    fetchReport();
    const interval = setInterval(fetchReport, 5000);
    return () => clearInterval(interval);
  }, [fetchReport]);

  const exportCsv = () => {
    fetch(`${API_URL}/attendance/export`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `attendance_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
      });
  };

  if (!report) return <div style={styles.panel}>Loading...</div>;

  return (
    <div style={styles.panel}>
      <div style={styles.dashHeader}>
        <h2 style={styles.panelTitle}>Today's Attendance — {report.date}</h2>
        <button style={styles.btnSecondary} onClick={exportCsv}>⬇ Export CSV</button>
      </div>
      <div style={styles.statsRow}>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, color: "#22c55e" }}>{report.present_count}</div>
          <div style={styles.statLabel}>Present</div>
        </div>
        <div style={styles.statBox}>
          <div style={{ ...styles.statNum, color: "#ef4444" }}>{report.absent_count}</div>
          <div style={styles.statLabel}>Absent</div>
        </div>
        <div style={styles.statBox}>
          <div style={styles.statNum}>{report.total_employees}</div>
          <div style={styles.statLabel}>Total Employees</div>
        </div>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Code</th>
            <th style={styles.th}>Status</th>
            <th style={styles.th}>Time</th>
          </tr>
        </thead>
        <tbody>
          {report.present.map((p, i) => (
            <tr key={`p${i}`}>
              <td style={styles.td}>{p.name}</td>
              <td style={styles.td}>{p.employee_code}</td>
              <td style={{ ...styles.td, color: "#22c55e" }}>Present</td>
              <td style={styles.td}>{p.time}</td>
            </tr>
          ))}
          {report.absent.map((a, i) => (
            <tr key={`a${i}`}>
              <td style={styles.td}>{a.name}</td>
              <td style={styles.td}>{a.employee_code}</td>
              <td style={{ ...styles.td, color: "#ef4444" }}>Absent</td>
              <td style={styles.td}>-</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(null);
  const [tab, setTab] = useState("dashboard");
  const [refreshKey, setRefreshKey] = useState(0);

  if (!token) return <LoginPage onLogin={setToken} />;

  return (
    <div style={styles.appWrap}>
      <div style={styles.header}>
        <h1 style={styles.headerTitle}>🎯 Face Recognition Attendance</h1>
        <div style={styles.tabs}>
          <button style={tab === "dashboard" ? styles.tabActive : styles.tab} onClick={() => setTab("dashboard")}>Dashboard</button>
          <button style={tab === "mark" ? styles.tabActive : styles.tab} onClick={() => setTab("mark")}>Mark Attendance</button>
          <button style={tab === "register" ? styles.tabActive : styles.tab} onClick={() => setTab("register")}>Register Employee</button>
          <button style={styles.logoutBtn} onClick={() => setToken(null)}>Logout</button>
        </div>
      </div>

      {tab === "dashboard" && <Dashboard key={refreshKey} token={token} />}
      {tab === "mark" && <MarkAttendance />}
      {tab === "register" && (
        <RegisterEmployee token={token} onDone={() => setRefreshKey((k) => k + 1)} />
      )}
    </div>
  );
}

const styles = {
  wrap: { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a" },
  card: { background: "#1e293b", padding: "40px", borderRadius: "16px", width: "320px" },
  title: { color: "#fff", textAlign: "center", marginBottom: "20px", fontSize: "22px" },
  input: { width: "100%", padding: "12px", marginBottom: "12px", borderRadius: "8px", border: "1px solid #334155", background: "#0f172a", color: "#fff", boxSizing: "border-box" },
  error: { color: "#f87171", fontSize: "13px", marginBottom: "10px" },
  btnPrimary: { width: "100%", padding: "12px", borderRadius: "8px", border: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: "600", cursor: "pointer", marginBottom: "10px" },
  btnSecondary: { width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #334155", background: "transparent", color: "#cbd5e1", cursor: "pointer", marginBottom: "10px" },
  switchText: { textAlign: "center", marginTop: "10px" },
  switchLink: { color: "#818cf8", cursor: "pointer", fontSize: "13px" },

  appWrap: { minHeight: "100vh", background: "#0f172a", padding: "24px" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "10px" },
  headerTitle: { color: "#fff", fontSize: "20px" },
  tabs: { display: "flex", gap: "8px" },
  tab: { padding: "8px 14px", borderRadius: "8px", border: "1px solid #334155", background: "transparent", color: "#94a3b8", cursor: "pointer" },
  tabActive: { padding: "8px 14px", borderRadius: "8px", border: "1px solid #6366f1", background: "#6366f1", color: "#fff", cursor: "pointer" },
  logoutBtn: { padding: "8px 14px", borderRadius: "8px", border: "1px solid #334155", background: "transparent", color: "#94a3b8", cursor: "pointer" },

  panel: { background: "#1e293b", borderRadius: "16px", padding: "24px", maxWidth: "600px" },
  panelTitle: { color: "#fff", marginBottom: "16px" },
  video: { width: "320px", height: "240px", borderRadius: "12px", background: "#000", marginBottom: "14px" },
  status: { color: "#cbd5e1", marginTop: "10px", fontSize: "14px" },

  resultBox: { marginTop: "16px", padding: "16px", borderRadius: "10px", border: "2px solid", background: "#0f172a" },
  resultName: { color: "#fff", fontSize: "18px", fontWeight: "700" },
  resultSub: { color: "#94a3b8", marginTop: "4px" },

  dashHeader: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  statsRow: { display: "flex", gap: "16px", margin: "16px 0" },
  statBox: { background: "#0f172a", padding: "14px 22px", borderRadius: "10px", textAlign: "center", flex: 1 },
  statNum: { fontSize: "26px", fontWeight: "700", color: "#fff" },
  statLabel: { fontSize: "12px", color: "#94a3b8" },
  table: { width: "100%", borderCollapse: "collapse", marginTop: "10px" },
  th: { textAlign: "left", color: "#94a3b8", padding: "8px", borderBottom: "1px solid #334155", fontSize: "13px" },
  td: { padding: "8px", borderBottom: "1px solid #1e293b", color: "#e2e8f0", fontSize: "14px" },
};
