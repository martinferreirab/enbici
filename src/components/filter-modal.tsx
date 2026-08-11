import Slider from '@react-native-community/slider';
import { Modal, Pressable, StyleSheet, Switch, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type RouteFilters = {
  elevationWeight: number;
  windWeight: number;
  allowParks: boolean;
  maxAgainstTrafficBlocks: 0 | 1 | 2 | 3;
};

type FilterModalProps = {
  visible: boolean;
  filters: RouteFilters;
  onChange: (filters: RouteFilters) => void;
  onClose: () => void;
};

const TRAFFIC_OPTIONS = [0, 1, 2, 3] as const;

export function FilterModal({ visible, filters, onChange, onClose }: FilterModalProps) {
  const theme = useTheme();

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <SafeAreaView edges={['bottom']}>
          <ThemedView type="background" style={styles.sheet}>
            <View style={styles.header}>
              <ThemedText type="subtitle">Filtros de ruta</ThemedText>
              <Pressable onPress={onClose} hitSlop={12}>
                <ThemedText type="link" themeColor="textSecondary">
                  Cerrar
                </ThemedText>
              </Pressable>
            </View>

            <View style={styles.row}>
              <ThemedText>Peso de elevación</ThemedText>
              <ThemedText themeColor="textSecondary">{filters.elevationWeight.toFixed(1)}</ThemedText>
            </View>
            <Slider
              minimumValue={0}
              maximumValue={10}
              step={0.5}
              value={filters.elevationWeight}
              onValueChange={(value) => onChange({ ...filters, elevationWeight: value })}
              minimumTrackTintColor={theme.text}
              maximumTrackTintColor={theme.backgroundSelected}
            />

            <View style={styles.row}>
              <ThemedText>Peso del viento</ThemedText>
              <ThemedText themeColor="textSecondary">{filters.windWeight.toFixed(1)}</ThemedText>
            </View>
            <Slider
              minimumValue={0}
              maximumValue={10}
              step={0.5}
              value={filters.windWeight}
              onValueChange={(value) => onChange({ ...filters, windWeight: value })}
              minimumTrackTintColor={theme.text}
              maximumTrackTintColor={theme.backgroundSelected}
            />

            <View style={[styles.row, styles.switchRow]}>
              <ThemedText>Permitir parques</ThemedText>
              <Switch
                value={filters.allowParks}
                onValueChange={(value) => onChange({ ...filters, allowParks: value })}
              />
            </View>

            <ThemedText style={styles.sectionLabel}>Tolerancia a contramano (cuadras)</ThemedText>
            <View style={styles.segmentedControl}>
              {TRAFFIC_OPTIONS.map((option) => {
                const selected = filters.maxAgainstTrafficBlocks === option;
                return (
                  <Pressable
                    key={option}
                    onPress={() => onChange({ ...filters, maxAgainstTrafficBlocks: option })}
                    style={[
                      styles.segment,
                      { backgroundColor: selected ? theme.text : theme.backgroundElement },
                    ]}>
                    <ThemedText
                      type="smallBold"
                      style={{ color: selected ? theme.background : theme.text }}>
                      {option}
                    </ThemedText>
                  </Pressable>
                );
              })}
            </View>
          </ThemedView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  sheet: {
    borderTopLeftRadius: Spacing.four,
    borderTopRightRadius: Spacing.four,
    padding: Spacing.four,
    gap: Spacing.two,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.two,
  },
  switchRow: {
    marginTop: Spacing.three,
  },
  sectionLabel: {
    marginTop: Spacing.three,
    marginBottom: Spacing.one,
  },
  segmentedControl: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  segment: {
    flex: 1,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
    alignItems: 'center',
  },
});
