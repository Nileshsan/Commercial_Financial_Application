import { useEffect } from 'react';
import { useRouter } from 'expo-router';

export default function AppIndex() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to dashboard when accessing the main app
    router.replace('/(app)/dashboard');
  }, []);

  return null;
}
