// Renders every [data-chart] element from a json_script spec built by web/charts.py.
// One shared theme here, so all charts look like one system.
(function () {
  "use strict";

  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();

  const INK = { primary: "#f0efec", secondary: "#c3c2b7", muted: "#898781" };
  const GRID = "#2c2c2a";
  const AXIS = "#383835";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const money = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK", maximumFractionDigits: 0 });
  const compact = new Intl.NumberFormat("nb-NO", { notation: "compact", maximumFractionDigits: 1 });

  function tooltip(trigger, isMoney) {
    return {
      trigger,
      backgroundColor: "rgba(12, 17, 32, 0.94)",
      borderColor: "rgba(255, 255, 255, 0.12)",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: INK.primary, fontFamily: token("--font"), fontSize: 12 },
      extraCssText: "border-radius: 10px; backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,.45);",
      valueFormatter: (v) => (isMoney ? money.format(v) : v),
      axisPointer: { type: trigger === "axis" ? "line" : "none", lineStyle: { color: "rgba(255,255,255,0.25)", width: 1 } },
    };
  }

  function gradient(hex) {
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: hex + "55" },
      { offset: 1, color: hex + "00" },
    ]);
  }

  function axes(spec) {
    const label = { color: INK.muted, fontFamily: token("--font"), fontSize: 11 };
    const cat = {
      type: "category", data: spec.x, boundaryGap: spec.kind === "bar", inverse: spec.horizontal,
      axisLine: { lineStyle: { color: AXIS } }, axisTick: { show: false },
      axisLabel: spec.horizontal ? { ...label, color: INK.secondary, fontSize: 12 } : label,
    };
    const val = {
      type: "value", splitNumber: 4,
      axisLabel: { ...label, formatter: (v) => compact.format(v) },
      splitLine: { lineStyle: { color: GRID, width: 1, type: "solid" } },
    };
    return spec.horizontal ? { xAxis: val, yAxis: cat } : { xAxis: cat, yAxis: val };
  }

  function build(spec) {
    const colors = spec.palette;
    const base = {
      backgroundColor: "transparent",
      color: colors,
      animation: !reduceMotion,
      animationDuration: 600,
      textStyle: { fontFamily: token("--font"), color: INK.secondary },
    };

    if (spec.kind === "heatmap") {
      const label = { color: INK.muted, fontFamily: token("--font"), fontSize: 11 };
      return {
        ...base,
        grid: { left: 8, right: 8, top: 8, bottom: 48, containLabel: true },
        xAxis: { type: "category", data: spec.x, axisLine: { show: false }, axisTick: { show: false }, axisLabel: label, splitArea: { show: false } },
        yAxis: { type: "category", data: spec.y, inverse: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { ...label, color: INK.secondary } },
        visualMap: {
          min: spec.min ?? 0, max: spec.max || 1, calculable: false, orient: "horizontal", left: "center", bottom: 0,
          itemWidth: 10, itemHeight: 160, inRange: { color: spec.palette },
          textStyle: { color: INK.muted, fontSize: 11 }, formatter: (v) => compact.format(v),
        },
        tooltip: {
          ...tooltip("item", spec.money),
          formatter: (p) => `${spec.y[p.value[1]]} · ${spec.x[p.value[0]]}<br><b>${spec.money ? money.format(p.value[2]) : p.value[2]}</b> ${spec.unit || "per day"}`,
        },
        series: [{
          type: "heatmap", data: spec.cells,
          itemStyle: { borderColor: token("--bg"), borderWidth: 2, borderRadius: 4 },
          emphasis: { itemStyle: { borderColor: INK.primary, borderWidth: 1 } },
        }],
      };
    }

    if (spec.kind === "sankey") {
      let i = 0;
      const nodes = spec.nodes.map((n) => ({
        name: n.name,
        itemStyle: { color: n.side === "middle" ? "#22d3ee" : n.side === "source" ? "#3987e5" : colors[(i++) % colors.length], borderWidth: 0 },
      }));
      return {
        ...base,
        tooltip: { ...tooltip("item", true), formatter: (p) => p.dataType === "edge"
          ? `${p.data.source} → ${p.data.target}<br><b>${money.format(p.data.value)}</b>`
          : `${p.name}<br><b>${money.format(p.value)}</b>` },
        series: [{
          type: "sankey", data: nodes, links: spec.links, nodeAlign: "justify", nodeGap: 10, nodeWidth: 10,
          left: 8, right: 140, top: 8, bottom: 8, draggable: false,
          lineStyle: { color: "gradient", opacity: 0.28, curveness: 0.5 },
          emphasis: { focus: "adjacency", lineStyle: { opacity: 0.55 } },
          label: { color: INK.secondary, fontFamily: token("--font"), fontSize: 12,
                   formatter: (p) => `${p.name}  ${compact.format(p.value)}` },
        }],
      };
    }

    if (spec.kind === "spark") {
      return {
        ...base,
        grid: { left: 2, right: 2, top: 4, bottom: 4 },
        xAxis: { type: "category", show: false, data: spec.x, boundaryGap: false },
        // y_max: small multiples share one scale from zero, so they can be compared.
        yAxis: spec.y_max ? { type: "value", show: false, min: 0, max: spec.y_max }
                          : { type: "value", show: false, scale: true },
        tooltip: { ...tooltip("axis", spec.money), axisPointer: { type: "none" } },
        series: [{
          type: "line", data: spec.series[0].data, name: spec.series[0].name,
          smooth: 0.3, symbol: "none", lineStyle: { width: 2, color: colors[0] },
          areaStyle: { color: gradient(colors[0]) },
        }],
      };
    }

    const many = spec.series.length > 1;
    return {
      ...base,
      ...axes(spec),
      grid: { left: 8, right: spec.horizontal ? 72 : 16, top: many ? 40 : 16, bottom: 4, containLabel: true },
      legend: many ? {
        top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, itemGap: 16,
        textStyle: { color: INK.secondary, fontSize: 12 },
      } : undefined,
      tooltip: tooltip(spec.kind === "bar" && !many ? "item" : "axis", spec.money),
      series: spec.series.map((s, i) => spec.kind === "bar" ? {
        type: "bar", name: s.name, data: s.data, barMaxWidth: spec.horizontal ? 16 : 24, barGap: "12%",
        stack: spec.stack ? "total" : undefined,
        // Stacked: a 2px surface gap between segments; only the top segment is rounded.
        itemStyle: spec.stack
          ? { borderColor: token("--bg"), borderWidth: 1,
              borderRadius: i === spec.series.length - 1 ? [4, 4, 0, 0] : 0 }
          : { borderRadius: spec.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
        label: spec.horizontal && !many ? {
          show: true, position: "right", color: INK.secondary, fontFamily: token("--mono"), fontSize: 11,
          formatter: (p) => money.format(p.value),
        } : undefined,
        emphasis: { focus: "series" },
      } : {
        type: "line", name: s.name, data: s.data, smooth: 0.25,
        symbol: "circle", symbolSize: 8, showSymbol: false,
        lineStyle: { width: 2, cap: "round", join: "round" },
        itemStyle: { borderColor: token("--bg"), borderWidth: 2 },
        areaStyle: spec.area ? { color: gradient(colors[i % colors.length]) } : undefined,
        emphasis: { focus: "series" },
      }),
    };
  }

  function renderAll(root) {
    root.querySelectorAll("[data-chart]").forEach((el) => {
      if (el.dataset.rendered) return;
      const src = document.getElementById(el.dataset.chart);
      if (!src) return;
      const chart = echarts.init(el, null, { renderer: "svg" });
      const spec = JSON.parse(src.textContent);
      chart.setOption(build(spec));
      if (spec.links) {
        // Drill-down: a click on a bar opens the transactions behind it.
        chart.on("click", (p) => {
          const url = (spec.links[p.seriesIndex] || [])[p.dataIndex];
          if (url) window.location.href = url;
        });
      }
      new ResizeObserver(() => chart.resize()).observe(el);
      el.dataset.rendered = "1";
    });
  }

  // Count-up for big numbers; final text is already in the HTML (works without JS).
  function countUp(root) {
    if (reduceMotion) return;
    root.querySelectorAll("[data-countup]").forEach((el) => {
      const target = Number(el.dataset.countup);
      if (!Number.isFinite(target)) return;
      const final = el.textContent;
      const fmt = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 0 });
      const t0 = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - t0) / 700);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = p < 1 ? fmt.format(target * eased) + " kr" : final;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  document.addEventListener("DOMContentLoaded", () => { renderAll(document); countUp(document); });
  document.addEventListener("htmx:afterSwap", (e) => { renderAll(e.target); countUp(e.target); });
})();
