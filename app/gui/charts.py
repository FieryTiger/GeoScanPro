from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec


_BINS   = [0, 0.1, 1, 10, 100, float('inf')]
_LABELS = ['<0.1', '0.1–1', '1–10', '10–100', '>100']
_BLUES  = ['#bfdbfe', '#93c5fd', '#60a5fa', '#3b82f6', '#2563eb']


def build_charts_figure(results: dict) -> Figure:
    fig = Figure(figsize=(9, 3.8))
    gs = GridSpec(1, 2, figure=fig, left=0.08, right=0.94, wspace=0.38, top=0.88, bottom=0.14)
    _draw_area_histogram(fig.add_subplot(gs[0, 0]), results)
    _draw_composition_pie(fig.add_subplot(gs[0, 1]), results)
    return fig


def _draw_area_histogram(ax, results):
    objects_data = results.get('objects_data', [])

    counts = [0] * len(_LABELS)
    for obj in objects_data:
        a = obj['area_km2']
        for i in range(len(_BINS) - 1):
            if _BINS[i] <= a < _BINS[i + 1]:
                counts[i] += 1
                break

    bars = ax.bar(_LABELS, counts, color=_BLUES, edgecolor='white', linewidth=0.7)
    ax.set_xlabel('Площадь, км²', fontsize=9)
    ax.set_ylabel('Количество объектов', fontsize=9)
    ax.set_title('Распределение объектов по площади', fontsize=10, fontweight='bold')
    ax.tick_params(labelsize=8)
    ax.set_ylim(0, max(counts, default=1) * 1.18)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(counts, default=1) * 0.02,
                str(count), ha='center', va='bottom', fontsize=8,
            )


def _draw_composition_pie(ax, results):
    water_pct = results.get('water_percentage', 0.0)
    cloud_pct = results.get('cloud_percentage', 0.0)
    land_pct  = results.get('land_percentage',  max(0.0, 100.0 - water_pct - cloud_pct))

    segments = [
        (water_pct, f'Вода\n{water_pct:.1f}%',   '#3b82f6'),
        (cloud_pct, f'Облака\n{cloud_pct:.1f}%',  '#94a3b8'),
        (land_pct,  f'Суша\n{land_pct:.1f}%',     '#86efac'),
    ]
    segments = [(s, l, c) for s, l, c in segments if s > 0.05]

    if not segments:
        ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center',
                transform=ax.transAxes, fontsize=10)
        ax.set_title('Состав сцены', fontsize=10, fontweight='bold')
        return

    sizes, labels, colors = zip(*segments)
    ax.pie(
        sizes, labels=labels, colors=colors,
        startangle=90,
        wedgeprops=dict(edgecolor='white', linewidth=1.2),
        textprops=dict(fontsize=8),
    )
    ax.set_title('Состав сцены', fontsize=10, fontweight='bold')
