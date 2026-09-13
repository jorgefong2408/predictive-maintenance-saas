# Wireframes (bocetos de baja fidelidad)

Boceto funcional de las 4 vistas principales del dashboard (Semana 6 las implementa en React).

## 1. Login
```
┌─────────────────────────────────────┐
│              [ Logo ]                │
│                                       │
│   Email     [_________________]      │
│   Password  [_________________]      │
│                                       │
│            [  Ingresar  ]            │
└─────────────────────────────────────┘
```

## 2. Lista de activos
```
┌───────────────────────────────────────────────────────────┐
│ PredictMaint     Acme Manufacturing ▾            [Alertas🔔3]│
├───────────────────────────────────────────────────────────┤
│ Activos                                    [+ Nuevo activo] │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ ● CRÍTICO   Mill-07     RUL: 3 días    Última alerta: 2m│ │
│ │ ● WARNING   Mill-03     RUL: 18 días   Última alerta: 1h│ │
│ │ ○ OK        Lathe-01    RUL: 92 días                    │ │
│ │ ○ OK        Press-12    RUL: 140 días                   │ │
│ └───────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

## 3. Detalle de activo
```
┌───────────────────────────────────────────────────────────┐
│ ← Activos / Mill-07                            ● CRÍTICO   │
├───────────────────────────────────────────────────────────┤
│ Torque (Nm)                                                │
│  60 ┤                                    ╭──╮ ← predicción │
│  40 ┤        ╭╮  ╭╮      ╭─╮        ╭───╯   ╰ RUL: 3 días  │
│  20 ┤───╮╭──╯╰──╯╰────╮╱   ╰──╲╱╲──╯                       │
│     └──────────────────────────────────────────── tiempo   │
│                                                              │
│ Temperatura de proceso (K)      Velocidad rotacional (rpm)  │
│  [gráfica]                       [gráfica]                  │
│                                                              │
│ Historial de alertas                                        │
│  • 2026-09-13 14:02  CRÍTICO  anomalía en torque + temp     │
│  • 2026-09-10 09:15  WARNING  RUL bajo umbral (20 días)     │
└───────────────────────────────────────────────────────────┘
```

## 4. Panel de alertas (tiempo real, WebSocket)
```
┌───────────────────────────────────────┐
│ Alertas activas (3)          [Marcar ✓]│
├───────────────────────────────────────┤
│ 🔴 Mill-07   Anomalía detectada  hace 2m│
│ 🟠 Mill-03   RUL < 20 días       hace 1h│
│ 🟠 Press-05  Drift de datos      hace 3h│
└───────────────────────────────────────┘
```

**Paleta de estado:** OK = verde/gris neutro · WARNING = ámbar · CRÍTICO = rojo. Mismo código de color en lista de activos, gráficas y panel de alertas.
