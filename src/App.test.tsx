import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the observer-first agent shell', async () => {
    render(<App />);

    expect(await screen.findByText('Desktop agent chat')).toBeInTheDocument();
    expect(await screen.findByPlaceholderText('Tell the agent what to do on this computer.')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open settings' })).toBeInTheDocument();
  });
});
