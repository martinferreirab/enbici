// La API key de Google Maps no vive en el repo: se lee de GOOGLE_MAPS_API_KEY
// (EAS env en builds en la nube, o variable de entorno en builds locales).
module.exports = ({ config }) => ({
  ...config,
  plugins: config.plugins.map((p) =>
    Array.isArray(p) && p[0] === "react-native-maps"
      ? [p[0], { ...p[1], androidGoogleMapsApiKey: process.env.GOOGLE_MAPS_API_KEY ?? p[1].androidGoogleMapsApiKey }]
      : p,
  ),
});
