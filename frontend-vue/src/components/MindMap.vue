<template>
  <div ref="container" class="mindmap-container"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import G6 from '@antv/g6';

const props = defineProps({
  data: {
    type: Object,
    required: true,
    default: () => ({ id: 'root', label: 'Root' })
  }
});

const container = ref(null);
let graph = null;
let themeObserver = null;

// Helper to get CSS variable value
const getCssVar = (name) => {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
};

const getThemeStyles = () => {
  const isDark = document.body.getAttribute('arco-theme') === 'dark';
  
  return {
    background: getCssVar('--bg-color') || (isDark ? '#0f1115' : '#ffffff'),
    nodeBg: getCssVar('--surface-1') || (isDark ? '#151a20' : '#f7f8fa'),
    nodeStroke: getCssVar('--card-border') || (isDark ? '#2a313b' : '#e5e6eb'),
    textMain: getCssVar('--text-main') || (isDark ? '#e5e7eb' : '#1a1a1a'),
    lineColor: getCssVar('--text-sub') || (isDark ? '#9aa4b2' : '#666666'),
    primary: getCssVar('--primary-color') || (isDark ? '#165dff' : '#165dff'),
  };
};

// Register custom node
const registerCustomNode = () => {
  G6.registerNode('mindmap-node', {
    draw(cfg, group) {
      const styles = getThemeStyles();
      const label = cfg.label || '';
      
      // Calculate width based on label
      // Approx 14px per char for font size 14, plus padding
      // Using canvas measureText would be more accurate but simple approximation works
      const fontSize = 14;
      const padding = [8, 16];
      const letterWidth = 14; // simplistic avg width for CN/EN mix
      // Simple length check: count non-ascii as 2, ascii as 1
      let len = 0;
      for (let i = 0; i < label.length; i++) {
        len += label.charCodeAt(i) > 255 ? 1 : 0.6;
      }
      const width = Math.max(80, len * fontSize + padding[1] * 2);
      const height = 36;
      
      const keyShape = group.addShape('rect', {
        attrs: {
          x: 0,
          y: -height / 2,
          width,
          height,
          radius: 6,
          fill: styles.nodeBg,
          stroke: styles.nodeStroke,
          lineWidth: 1,
          cursor: 'pointer',
        },
        name: 'key-shape',
      });

      group.addShape('text', {
        attrs: {
          text: label,
          x: width / 2,
          y: 0,
          textAlign: 'center',
          textBaseline: 'middle',
          fill: styles.textMain,
          fontSize: fontSize,
          cursor: 'pointer',
        },
        name: 'label-shape',
      });

      // Collapse marker
      if (cfg.children && cfg.children.length > 0) {
        group.addShape('marker', {
          attrs: {
            x: width,
            y: 0,
            r: 8,
            symbol: cfg.collapsed ? G6.Marker.expand : G6.Marker.collapse,
            stroke: styles.lineColor,
            fill: styles.nodeBg,
            lineWidth: 1,
            cursor: 'pointer',
          },
          name: 'collapse-icon',
        });
      }

      return keyShape;
    },
    update(cfg, item) {
      const group = item.getContainer();
      const styles = getThemeStyles();
      
      const keyShape = group.find(ele => ele.get('name') === 'key-shape');
      const labelShape = group.find(ele => ele.get('name') === 'label-shape');
      const collapseIcon = group.find(ele => ele.get('name') === 'collapse-icon');

      const label = cfg.label || '';
      const fontSize = 14;
      const padding = [8, 16];
      let len = 0;
      for (let i = 0; i < label.length; i++) {
        len += label.charCodeAt(i) > 255 ? 1 : 0.6;
      }
      const width = Math.max(80, len * fontSize + padding[1] * 2);
      const height = 36;

      keyShape.attr({
        width,
        height,
        y: -height / 2,
        fill: styles.nodeBg,
        stroke: styles.nodeStroke,
      });

      labelShape.attr({
        text: label,
        x: width / 2,
        fill: styles.textMain,
      });

      if (collapseIcon) {
        collapseIcon.attr({
          x: width,
          symbol: cfg.collapsed ? G6.Marker.expand : G6.Marker.collapse,
          stroke: styles.lineColor,
          fill: styles.nodeBg,
        });
      } else if (cfg.children && cfg.children.length > 0) {
         // Add if appeared
         group.addShape('marker', {
          attrs: {
            x: width,
            y: 0,
            r: 8,
            symbol: cfg.collapsed ? G6.Marker.expand : G6.Marker.collapse,
            stroke: styles.lineColor,
            fill: styles.nodeBg,
            lineWidth: 1,
            cursor: 'pointer',
          },
          name: 'collapse-icon',
        });
      }
    }
  }, 'single-node');
};

const initGraph = () => {
  if (!container.value) return;
  
  registerCustomNode();
  
  const width = container.value.clientWidth;
  const height = container.value.clientHeight || 500;
  const styles = getThemeStyles();

  graph = new G6.TreeGraph({
    container: container.value,
    width,
    height,
    modes: {
      default: [
        'drag-canvas',
        'zoom-canvas',
      ],
    },
    defaultNode: {
      type: 'mindmap-node',
    },
    defaultEdge: {
      type: 'cubic-horizontal',
      style: {
        stroke: styles.lineColor,
        lineWidth: 2,
      },
    },
    layout: {
      type: 'mindmap',
      direction: 'H',
      getHeight: () => 36,
      getWidth: (node) => {
          const label = node.label || '';
          let len = 0;
          for (let i = 0; i < label.length; i++) {
            len += label.charCodeAt(i) > 255 ? 1 : 0.6;
          }
          return Math.max(80, len * 14 + 32) + 20; // +20 for gap/icon
      },
      getVGap: () => 16,
      getHGap: () => 50,
      getSide: () => 'right',
    },
  });

  // Handle collapse icon click
  graph.on('collapse-icon:click', (e) => {
    e.propagationStopped = true;
    const item = e.item;
    const model = item.getModel();
    graph.updateItem(item, {
      collapsed: !model.collapsed,
    });
    graph.layout();
  });

  graph.data(props.data);
  graph.render();
  graph.fitView();
};

const updateGraphTheme = () => {
  if (!graph) return;
  const styles = getThemeStyles();
  
  // Update edges
  graph.getEdges().forEach(edge => {
    graph.updateItem(edge, {
      style: {
        stroke: styles.lineColor,
      },
    });
  });
  
  // Update nodes (custom node update logic handles styles)
  graph.getNodes().forEach(node => {
    graph.updateItem(node, {
      // Trigger update
    });
  });
  
  graph.paint();
};

watch(() => props.data, (newData) => {
  if (graph) {
    graph.changeData(newData);
    graph.fitView();
  }
});

const handleResize = () => {
  if (!graph || !container.value) return;
  const width = container.value.clientWidth;
  const height = container.value.clientHeight;
  // Ensure we have valid dimensions
  if (width === 0 || height === 0) return;
  
  graph.changeSize(width, height);
  graph.fitView();
};

let resizeObserver = null;

onMounted(() => {
  // Delay slightly to ensure fonts loaded / styles ready
  setTimeout(() => {
     initGraph();
  }, 100);
  
  // Use ResizeObserver for more robust size detection
  resizeObserver = new ResizeObserver(() => {
    // Use requestAnimationFrame to avoid "ResizeObserver loop limit exceeded"
    requestAnimationFrame(() => {
      handleResize();
    });
  });
  
  if (container.value) {
    resizeObserver.observe(container.value);
  }
  
  themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === 'arco-theme') {
         // Re-render or update styles
         // Since custom node uses getThemeStyles() in draw/update, calling graph.refresh() might be needed
         // or just updating all items.
         // Simpler to just re-layout or update items.
         updateGraphTheme();
      }
    });
  });
  
  themeObserver.observe(document.body, {
    attributes: true,
    attributeFilter: ['arco-theme'],
  });
});

onUnmounted(() => {
  if (graph) {
    graph.destroy();
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  if (themeObserver) {
    themeObserver.disconnect();
  }
});
</script>

<style scoped>
.mindmap-container {
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: var(--bg-color);
}
</style>
