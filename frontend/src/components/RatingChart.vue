<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])
const props = defineProps<{ ratings: Array<{ rating: number; total: number }> }>()
const option = computed(() => ({
  grid: { left: 16, right: 12, top: 20, bottom: 28, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'category',
    data: props.ratings.map((item) => `${item.rating}★`),
    axisLabel: { color: '#8ea3bd' },
    axisLine: { lineStyle: { color: '#26394f' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#8ea3bd', formatter: (value: number) => `${Math.round(value / 1000)}k` },
    splitLine: { lineStyle: { color: '#1d3045' } },
  },
  series: [
    {
      type: 'bar',
      data: props.ratings.map((item) => item.total),
      barWidth: '48%',
      itemStyle: {
        color: '#5cd6ff',
        borderRadius: [7, 7, 2, 2],
      },
    },
  ],
}))
</script>

<template><VChart class="chart" :option="option" autoresize /></template>
