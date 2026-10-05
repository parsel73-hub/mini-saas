/*
 * Chart.js initialisation helper (Этап 5 — статистика).
 *
 * Any <script type="application/json" data-chart data-canvas="<canvas id>"
 * data-type="pie|bar"> element is parsed as chart data and rendered into the
 * referenced canvas. This keeps survey data out of inline JS while avoiding
 * hand-written per-chart code.
 */
(function () {
    "use strict";

    var PALETTE = [
        "#2c7be5", "#28a745", "#f6a821", "#e63757",
        "#6f42c1", "#20c997", "#fd7e14", "#6c757d"
    ];

    function buildChart(el) {
        var canvas = document.getElementById(el.dataset.canvas);
        if (!canvas || typeof Chart === "undefined") {
            return;
        }

        var payload;
        try {
            payload = JSON.parse(el.textContent);
        } catch (err) {
            return;
        }

        var labels = payload.labels || [];
        var values = payload.values || [];
        var colors = labels.map(function (_, i) {
            return PALETTE[i % PALETTE.length];
        });

        new Chart(canvas.getContext("2d"), {
            type: el.dataset.type || "pie",
            data: {
                labels: labels,
                datasets: [{
                    label: payload.label || "Ответы",
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: labels.length > 6 ? "bottom" : "right" },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var percent = (payload.percents || [])[ctx.dataIndex];
                                var suffix = percent === undefined ? "" : " (" + percent + "%)";
                                return ctx.label + ": " + ctx.parsed + suffix;
                            }
                        }
                    }
                }
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document
            .querySelectorAll('script[type="application/json"][data-chart]')
            .forEach(buildChart);
    });
})();
