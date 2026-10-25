import { Platform } from "react-native";

export const cardShadow = Platform.select({
  web: { boxShadow: "0px 2px 8px rgba(0,0,0,0.15)" },
  android: { elevation: 6 },
  default: { shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.15, shadowRadius: 8 },
});
