static int swi(int c) {
    switch (c) {
        case 0: return 42;
        case 1: return 43;
        case 2: return 44;
        case 3: return 45;
        default: break;
    }
    return -1;
}

int main() {
    volatile int k;
    k=swi(k);
    return k;
}
