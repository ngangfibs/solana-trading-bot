import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dropout, Dense

class LSTMModel:
    def __init__(self, sequence_length=60, prediction_horizon=12):
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.model = self._build_model()
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        
    def _build_model(self):
        """Build and compile the LSTM model"""
        model = Sequential([
            LSTM(units=50, return_sequences=True, input_shape=(self.sequence_length, 7)),
            Dropout(0.2),
            LSTM(units=50, return_sequences=False),
            Dropout(0.2),
            Dense(units=self.prediction_horizon)
        ])
        
        model.compile(optimizer='adam', loss='mean_squared_error')
        return model
        
    def preprocess_data(self, data):
        """Preprocess data for LSTM model"""
        # Extract features
        features = data[['close', 'volume', 'rsi', 'ma20', 'ma50', 'upper_bb', 'lower_bb']].values
        
        # Scale features
        scaled_features = self.scaler.fit_transform(features)
        
        # Create sequences
        X, y = [], []
        for i in range(self.sequence_length, len(scaled_features) - self.prediction_horizon):
            X.append(scaled_features[i-self.sequence_length:i])
            y.append(scaled_features[i:i+self.prediction_horizon, 0])  # Predict close price
            
        return np.array(X), np.array(y)
        
    def train(self, data, epochs=50, batch_size=32, validation_split=0.2):
        """Train the LSTM model on historical data"""
        X, y = self.preprocess_data(data)
        
        # Split into training and validation sets
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_valid = X[:split_idx], X[split_idx:]
        y_train, y_valid = y[:split_idx], y[split_idx:]
        
        # Train model
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_valid, y_valid),
            verbose=1
        )
        
        return history
        
    def predict(self, data):
        """Generate price predictions for the given data"""
        # Ensure we have enough data
        if len(data) < self.sequence_length:
            raise ValueError(f"Not enough data points. Need at least {self.sequence_length}.")
            
        # Preprocess the latest data sequence
        features = data[-self.sequence_length:][['close', 'volume', 'rsi', 'ma20', 'ma50', 'upper_bb', 'lower_bb']].values
        scaled_features = self.scaler.transform(features)
        
        # Reshape for prediction
        X = np.array([scaled_features])
        
        # Make prediction
        scaled_prediction = self.model.predict(X)[0]
        
        # Inverse transform to get actual price predictions
        # This is simplified - in practice, would need to handle the multi-dimensional inverse transform
        prediction = self.scaler.inverse_transform(
            np.concatenate([scaled_prediction.reshape(-1, 1), np.zeros((self.prediction_horizon, 6))], axis=1)
        )[:, 0]
        
        return prediction
