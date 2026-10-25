import { StyleSheet } from "react-native";
import { WebView } from "react-native-webview";

const IDLE_HTML = `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#m{height:100%;margin:0}</style></head><body><div id="m"></div>
<script>var m=L.map('m').setView([-34.9011,-56.1645],13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19}).addTo(m);</script></body></html>`;

export function MapViewer({ uri }: { uri: string | null }) {
  return (
    <WebView
      style={StyleSheet.absoluteFill}
      originWhitelist={["*"]}
      source={uri ? { uri } : { html: IDLE_HTML }}
      key={uri ?? "idle"}
      javaScriptEnabled
      domStorageEnabled
      mixedContentMode="always"
    />
  );
}
