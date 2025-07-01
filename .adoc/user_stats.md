<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    /* Palette douce */
    :root {
      --bg-page: #f0f2f5;
      --bg-card: #ffffff;
      --primary: #7262ff;
      --secondary: #ff8c94;
      --text-main: #2f2f2f;
      --text-muted: #7a7a7a;
      --accent-light: #e0d7ff;
      --accent-light-2: #ffd9dc;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      background: var(--bg-page);
      font-family: "Segoe UI", sans-serif;
      color: var(--text-main);
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }
    .card {
      width: 600px;
      background: var(--bg-card);
      border-radius: 16px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      overflow: hidden;
    }
    .header {
      background: linear-gradient(135deg, var(--primary), var(--secondary));
      padding: 24px;
      text-align: center;
      color: #fff;
    }
    .header img {
      width: 120px;
      height: 120px;
      border-radius: 50%;
      border: 4px solid #fff;
      object-fit: cover;
      margin-bottom: 12px;
    }
    .header h1 {
      font-size: 28px;
      margin-bottom: 4px;
    }
    .header .sub {
      font-size: 14px;
      opacity: 0.8;
    }
    .stats {
      padding: 24px;
    }
    .stat-item {
      display: flex;
      align-items: center;
      margin-bottom: 16px;
    }
    .stat-item:last-child { margin-bottom: 0; }
    .stat-item .icon {
      font-size: 24px;
      width: 32px;
      text-align: center;
      margin-right: 12px;
      color: var(--primary);
    }
    .stat-item .label {
      flex: 1;
      font-size: 16px;
    }
    .stat-item .value {
      font-weight: bold;
      font-size: 16px;
      color: var(--text-muted);
    }
    .progress-bar {
      position: relative;
      background: var(--accent-light);
      border-radius: 8px;
      height: 12px;
      overflow: hidden;
      margin-top: 4px;
    }
    .progress-bar .fill {
      background: var(--primary);
      height: 100%;
      width: 0%;
      transition: width 0.5s ease;
    }
    .footer {
      text-align: center;
      padding: 16px;
      font-size: 12px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <img src="{{ avatar_url }}" alt="Avatar">
      <h1>{{ username }}</h1>
      <div class="sub">{{ server_name }}</div>
    </div>
    <div class="stats">
      <div class="stat-item">
        <span class="icon">✉️</span>
        <div class="label">Messages totaux</div>
        <div class="value">{{ total_messages }}</div>
      </div>
      <div class="progress-bar">
        <div class="fill" style="width: {{ (total_messages / max_messages * 100)|round(0) }}%;"></div>
      </div>

      <div class="stat-item">
        <span class="icon">🔊</span>
        <div class="label">Minutes vocales</div>
        <div class="value">{{ total_voice }}</div>
      </div>
      <div class="progress-bar">
        <div class="fill" style="width: {{ (total_voice / max_voice * 100)|round(0) }}%; background: var(--secondary);"></div>
      </div>

      <div class="stat-item">
        <span class="icon">📈</span>
        <div class="label">Messages hier / aujourd’hui</div>
        <div class="value">{{ m1 }}/{{ m0 }}</div>
      </div>

      <div class="stat-item">
        <span class="icon">⏱️</span>
        <div class="label">Voix hier / aujourd’hui</div>
        <div class="value">{{ v1 }}/{{ v0 }}</div>
      </div>
    </div>
    <div class="footer">
      Généré le {{ generated_on }} • Elda-Bot
    </div>
  </div>
</body>
</html>
