import React, { useEffect, useState } from 'react';
import {
  Modal,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Colors, FontSizes, Spacing, Radii } from '../constants/theme';
import { getProjects, Project, configure } from '../services/geraldApi';
import { useConversationStore } from '../store/conversationStore';

interface Props {
  visible: boolean;
  onClose: () => void;
}

export default function ProjectSelectorModal({ visible, onClose }: Props) {
  const { project, setProject, baseUrl } = useConversationStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (visible) {
      loadProjects();
    }
  }, [visible]);

  async function loadProjects() {
    setLoading(true);
    setError('');
    configure(baseUrl);
    try {
      const data = await getProjects();
      setProjects(data);
      if (!project && data.length > 0) {
        setProject(data[0].name);
      }
    } catch {
      setError('Could not load projects. Check Gerald is running.');
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }

  function selectProject(name: string) {
    setProject(name);
    onClose();
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <TouchableOpacity style={styles.overlay} onPress={onClose} activeOpacity={1}>
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <Text style={styles.title}>Select Project</Text>

          {loading && (
            <ActivityIndicator color={Colors.accent} style={styles.loader} />
          )}

          {!!error && <Text style={styles.error}>{error}</Text>}

          <FlatList
            data={projects}
            keyExtractor={(item) => item.name}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[
                  styles.row,
                  item.name === project && styles.rowSelected,
                ]}
                onPress={() => selectProject(item.name)}
                activeOpacity={0.7}
              >
                <View style={styles.rowContent}>
                  <Text style={styles.projectName}>{item.name}</Text>
                  <Text style={styles.projectPath} numberOfLines={1}>
                    {item.path}
                  </Text>
                </View>
                {item.name === project && (
                  <Text style={styles.checkmark}>✓</Text>
                )}
              </TouchableOpacity>
            )}
            ListEmptyComponent={
              !loading ? (
                <Text style={styles.empty}>No projects found</Text>
              ) : null
            }
          />
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radii.lg,
    borderTopRightRadius: Radii.lg,
    padding: Spacing.lg,
    maxHeight: '60%',
  },
  handle: {
    width: 40,
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: Spacing.lg,
  },
  title: {
    color: Colors.textPrimary,
    fontSize: FontSizes.lg,
    fontWeight: '700',
    marginBottom: Spacing.md,
  },
  loader: {
    marginVertical: Spacing.lg,
  },
  error: {
    color: Colors.error,
    fontSize: FontSizes.sm,
    marginBottom: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.sm,
    borderRadius: Radii.sm,
    marginBottom: Spacing.xs,
  },
  rowSelected: {
    backgroundColor: Colors.surfaceElevated,
  },
  rowContent: {
    flex: 1,
  },
  projectName: {
    color: Colors.textPrimary,
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  projectPath: {
    color: Colors.textSecondary,
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  checkmark: {
    color: Colors.accent,
    fontSize: FontSizes.lg,
    fontWeight: 'bold',
    marginLeft: Spacing.sm,
  },
  empty: {
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
});
