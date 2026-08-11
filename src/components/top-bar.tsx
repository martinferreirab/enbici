import { Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type TopBarProps = {
  originText: string;
  destText: string;
  onOriginChange: (text: string) => void;
  onDestChange: (text: string) => void;
  onUseCurrentLocation: () => void;
  onOpenFilters: () => void;
  onSubmit: () => void;
  loading: boolean;
};

export function TopBar({
  originText,
  destText,
  onOriginChange,
  onDestChange,
  onUseCurrentLocation,
  onOpenFilters,
  onSubmit,
  loading,
}: TopBarProps) {
  const theme = useTheme();

  return (
    <ThemedView type="background" style={styles.card}>
      <View style={styles.inputRow}>
        <TextInput
          value={originText}
          onChangeText={onOriginChange}
          placeholder="Origen"
          placeholderTextColor={theme.textSecondary}
          style={[styles.input, { color: theme.text }]}
          returnKeyType="next"
        />
        <Pressable onPress={onUseCurrentLocation} hitSlop={8}>
          <ThemedText type="linkPrimary">GPS</ThemedText>
        </Pressable>
      </View>

      <View style={styles.divider} />

      <View style={styles.inputRow}>
        <TextInput
          value={destText}
          onChangeText={onDestChange}
          placeholder="Destino"
          placeholderTextColor={theme.textSecondary}
          style={[styles.input, { color: theme.text }]}
          returnKeyType="search"
          onSubmitEditing={onSubmit}
        />
        <Pressable onPress={onOpenFilters} hitSlop={8}>
          <ThemedText type="small">Filtros</ThemedText>
        </Pressable>
      </View>

      <Pressable
        onPress={onSubmit}
        disabled={loading}
        style={[styles.submitButton, { backgroundColor: theme.text, opacity: loading ? 0.6 : 1 }]}>
        <ThemedText type="smallBold" style={{ color: theme.background }}>
          {loading ? 'Calculando...' : 'Calcular ruta'}
        </ThemedText>
      </Pressable>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: Spacing.four,
    padding: Spacing.three,
    gap: Spacing.one,
    ...Platform.select({
      web: { boxShadow: '0px 4px 10px rgba(0,0,0,0.15)' },
      android: { elevation: 6 },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.15,
        shadowRadius: 10,
      },
    }),
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  input: {
    flex: 1,
    fontSize: 16,
    paddingVertical: Spacing.one,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(128,128,128,0.3)',
  },
  submitButton: {
    marginTop: Spacing.two,
    borderRadius: Spacing.two,
    paddingVertical: Spacing.two,
    alignItems: 'center',
  },
});
