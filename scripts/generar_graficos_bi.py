import os
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams.update({"font.size": 10, "figure.autolayout": True})

output_dir = Path(r"C:\Users\nelca\Desktop\db3\BaseDeDatosNoRelacional\evidencias\graficos_bi")
output_dir.mkdir(parents=True, exist_ok=True)

df_fact = pd.read_csv(r"C:\Users\nelca\Desktop\db3\BaseDeDatosNoRelacional\datos_bi\fact_ordenes_bi.csv")
df_bridge = pd.read_csv(r"C:\Users\nelca\Desktop\db3\BaseDeDatosNoRelacional\datos_bi\bridge_seguimiento_historial.csv")

# 1. Gráfico 1: Ingresos y Pérdidas por Zona y Estado
plt.figure(figsize=(9, 5))
pivot_zona = df_fact.pivot_table(index="zona", columns="estado", values="total", aggfunc="sum", fill_value=0) / 1e6
colores = {"Entregado": "#2ecc71", "Cancelado": "#e74c3c", "En preparación": "#f39c12", "En tránsito": "#3498db"}
cols_presentes = [c for c in ["Entregado", "Cancelado", "En preparación", "En tránsito"] if c in pivot_zona.columns]
pivot_zona[cols_presentes].plot(kind="bar", stacked=True, color=[colores[c] for c in cols_presentes], figsize=(9, 5))
plt.title("Ingresos y Pérdidas por Zona Geográfica (Millones CLP)", fontsize=13, weight="bold")
plt.xlabel("Zona Geográfica")
plt.ylabel("Millones CLP ($M)")
plt.legend(title="Estado de Orden")
plt.xticks(rotation=0)
plt.savefig(output_dir / "grafico_1_ingresos_por_zona.png", dpi=300)
plt.close()

# 2. Gráfico 2: Evolución Mensual de Órdenes por Estado
plt.figure(figsize=(9, 5))
pivot_mes = df_fact.pivot_table(index="mes", columns="estado", values="_id", aggfunc="count", fill_value=0)
for c in cols_presentes:
    if c in pivot_mes.columns:
        plt.plot(pivot_mes.index, pivot_mes[c], marker="o", label=c, color=colores[c], linewidth=2.5)
plt.title("Evolución Mensual de Órdenes según Estado", fontsize=13, weight="bold")
plt.xlabel("Mes (AAAA-MM)")
plt.ylabel("Cantidad de Órdenes")
plt.legend(title="Estado")
plt.savefig(output_dir / "grafico_2_evolucion_mensual.png", dpi=300)
plt.close()

# 3. Gráfico 3: Embudo de Eventos en Historial (bridge_seguimiento_historial)
plt.figure(figsize=(8, 4.5))
orden_etapas = ["En preparación", "Despachado", "En tránsito", "Entregado"]
conteo_etapas = df_bridge["estado_historial"].value_counts().reindex(orden_etapas).fillna(0)
barras = plt.barh(orden_etapas, conteo_etapas, color=["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"])
plt.title("Embudo Operativo: Eventos Registrados en Historial (N=302)", fontsize=13, weight="bold")
plt.xlabel("Cantidad de Eventos")
for bar in barras:
    w = bar.get_width()
    plt.text(w + 2, bar.get_y() + bar.get_height()/2, f"{int(w)} eventos", va="center", weight="bold")
plt.xlim(0, max(conteo_etapas) * 1.2)
plt.gca().invert_yaxis()
plt.savefig(output_dir / "grafico_3_embudo_seguimiento.png", dpi=300)
plt.close()

# 4. Gráfico 4: Banderas de Calidad de Datos / Auditoría Técnica
plt.figure(figsize=(9, 4.5))
flags = {
    "Envío < Registro": int(df_fact["flag_envio_previo_registro"].sum()),
    "Orden != Seguimiento": int(df_fact["flag_orden_vs_seguimiento"].sum()),
    "Valorada no entregada": int(df_fact["flag_valorada_no_entregada"].sum()),
    "Seg. != Último historial": int(df_fact["flag_seguimiento_vs_historial"].sum()),
    "Val. Contradictoria": int(df_fact["flag_valoracion_contradictoria"].sum()),
    "Caso C11 (Prep c/ Tráns.)": int(df_fact["flag_c11"].sum()),
}
df_flags = pd.Series(flags).sort_values(ascending=True)
plt.barh(df_flags.index, df_flags.values, color="#e67e22")
plt.title("Auditoría Técnica: Inconsistencias Detectadas en MongoDB Atlas (%)", fontsize=13, weight="bold")
plt.xlabel("Porcentaje sobre 100 Órdenes (%)")
for i, v in enumerate(df_flags.values):
    plt.text(v + 1, i, f"{v}%", va="center", weight="bold")
plt.xlim(0, 100)
plt.savefig(output_dir / "grafico_4_auditoria_calidad.png", dpi=300)
plt.close()

print("Graficos generados exitosamente en:", output_dir)
