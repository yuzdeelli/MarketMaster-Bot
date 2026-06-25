import numpy as np
import pandas as pd
from datetime import datetime

try:
    from sklearn.model_selection import train_test_split, KFold, cross_val_score, GridSearchCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from core.database import DatabaseManager


class MarketPredictor:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.model = None
        self.best_params = None

    def load_and_prepare_data(self, item_name, item_lvl, start_date=None, end_date=None):
        try:
            with self.db.get_connection() as conn:
                query = """
                    SELECT server, type, price, timestamp 
                    FROM prices 
                    WHERE LOWER(TRIM(item_name)) = LOWER(TRIM(?)) 
                      AND LOWER(TRIM(item_lvl)) = LOWER(TRIM(?))
                """
                params = [item_name, item_lvl]

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp ASC"

                df = pd.read_sql_query(query, conn, params=tuple(params))

            if len(df) < 20:
                print(f"⚠️ {item_name} {item_lvl} için yetersiz veri var (Mevcut: {len(df)} satır). Güvenilir bir tahmin için en az 20 kayıt olmalı.")
                return None, None

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek

            df['is_sell'] = (df['type'].str.capitalize() == 'Sell').astype(int)
            df['server_encoded'] = df['server'].astype('category').cat.codes

            df['next_price'] = df['price'].shift(-1)
            df['target'] = (df['next_price'] > df['price']).astype(int)

            df = df.dropna()

            X = df[['price', 'hour', 'day_of_week', 'is_sell', 'server_encoded']]
            y = df['target']

            return X, y

        except Exception as e:
            print(f"❌ Veri hazırlama hatası: {e}")
            return None, None

    def train_and_evaluate(self, item_name, item_lvl, start_date=None, end_date=None):
        if not SKLEARN_AVAILABLE:
            print("sklearn yuklu degil. ML tahminleri kullanilamiyor.")
            return None

        X, y = self.load_and_prepare_data(item_name, item_lvl, start_date, end_date)
        if X is None or y is None:
            return

        print(f"\n==================================================")
        print(f"🚀 {item_name} {item_lvl} İçin Yapay Zeka Analizi Başladı")
        print(f"==================================================")
        print(f"📊 Toplam Analiz Edilen Veri Satırı: {len(X)}")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        base_clf = RandomForestClassifier(random_state=42)
        base_clf.fit(X_train, y_train)
        y_pred = base_clf.predict(X_test)

        print("\n--- 📌 1. Holdout (Test Seti) Başarı Metrikleri ---")
        print(f"Doğruluk (Accuracy)   : {accuracy_score(y_test, y_pred):.2f}")
        print(f"Keskinlik (Precision) : {precision_score(y_test, y_pred, zero_division=0):.2f}  <-- (Al dediğinin yüzde kaçı doğru çıktı)")
        print(f"Duyarlılık (Recall)   : {recall_score(y_test, y_pred, zero_division=0):.2f}  <-- (Yükseliş fırsatlarının yüzde kaçını yakaladı)")
        print(f"F1-Skoru (F1-Score)   : {f1_score(y_test, y_pred, zero_division=0):.2f}")

        print("\nKarmaşıklık Matrisi (Confusion Matrix):")
        print(confusion_matrix(y_test, y_pred))

        print("\n--- 📌 2. 5-Fold Cross Validation Güvenilirlik Testi ---")
        kf = KFold(n_splits=5, shuffle=True, random_state=42)

        cv_scores = cross_val_score(base_clf, X, y, cv=kf, scoring='f1', error_score='raise')
        scores_str = np.array2string(cv_scores, formatter={'float_fn': lambda x: f'{x:.2f}'})
        print(f"Katmanlarin F1 Skorlari : {scores_str}")
        print(f"Ortalama Guven Skoru    : {cv_scores.mean():.2f} (+/- {cv_scores.std() * 2:.2f})")

        if cv_scores.std() > 0.15:
            print("⚠️ UYARI: Varyans yüksek! Model istikrarsız sonuçlar veriyor (Overfitting riski).")
        else:
            print("✅ Varyans düşük: Model farklı veri gruplarında istikrarlı/güvenilir çalışıyor.")

        print("\n--- 📌 3. Hiperparametre Tuning (Grid Search) Başlatılıyor ---")
        param_grid = {
            'n_estimators': [50, 100],
            'max_depth': [5, 10, None],
            'min_samples_split': [2, 5]
        }

        grid_search = GridSearchCV(estimator=RandomForestClassifier(random_state=42),
                                   param_grid=param_grid,
                                   cv=3,
                                   scoring='f1',
                                   n_jobs=-1)
        grid_search.fit(X_train, y_train)

        self.best_params = grid_search.best_params_
        self.model = grid_search.best_estimator_

        print(f"En İyi Parametreler: {self.best_params}")

        tuned_preds = self.model.predict(X_test)
        print(f"🚀 TUNED MODEL EN YÜKSEK F1-SKORU: {f1_score(y_test, tuned_preds, zero_division=0):.2f}")

        return self.model
